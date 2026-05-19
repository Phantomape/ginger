"""exp-20260518-019: core-misfit conditioned short shadow.

Follow-up to exp-20260517-003. The previous fixed-10d short shadow was
profitable but failed because only old_thin was positive. This experiment keeps
the source signals and fixed-10d short exit locked, then sweeps one
production-visible condition gate to see whether the inverse edge becomes less
window-concentrated.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260518-019"
EXPERIMENT_SLUG = "core_misfit_conditioned_short_shadow"
SHORT_SOURCE_EXPERIMENT_ID = "exp-20260517-003"
MISFIT_SOURCE_EXPERIMENT_ID = "exp-20260516-043"

SHORT_ARTIFACT = (
    base.REPO_ROOT
    / "data"
    / "experiments"
    / SHORT_SOURCE_EXPERIMENT_ID
    / "core_misfit_short_shadow_backtest.json"
)
MISFIT_ARTIFACT = (
    base.REPO_ROOT
    / "data"
    / "experiments"
    / MISFIT_SOURCE_EXPERIMENT_ID
    / "core_misfit_paper_sleeve.json"
)

PRIMARY_MISFIT_TICKERS = ("TSM", "ISRG", "V", "DDOG")
LOCKED_SHORT_POLICY = "fixed_10d"
STARTING_CAPITAL = 100000.0
MIN_TRADE_COUNT = 4
MIN_POSITIVE_WINDOWS = 2
MAX_ACCEPTABLE_WORST_TRADE = -0.10
MAX_AGGREGATE_PNL_HAIRCUT_VS_IDENTITY = 0.20


Condition = Callable[[dict[str, Any]], bool]


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True)
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


def _money(value: Any) -> float:
    try:
        out = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(out):
        return 0.0
    return round(out, 2)


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, digits)
    return value


def _load_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads(SHORT_ARTIFACT.read_text(encoding="utf-8")),
        json.loads(MISFIT_ARTIFACT.read_text(encoding="utf-8")),
    )


def _candidate_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("ticker") or "").upper(),
        str(row.get("window") or ""),
        str(row.get("signal_date") or ""),
    )


def _joined_rows(
    short_payload: dict[str, Any],
    misfit_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates = {
        _candidate_key(row): row
        for row in misfit_payload["paper_surfaces"]["paper_candidate_records"]
        if str(row.get("ticker") or "").upper() in PRIMARY_MISFIT_TICKERS
    }
    rows = []
    for outcome in short_payload["short_policy_outcomes"][LOCKED_SHORT_POLICY]:
        candidate = candidates.get(_candidate_key(outcome)) or {}
        rows.append({**outcome, "candidate": candidate})
    return rows


def _risk_multipliers(row: dict[str, Any]) -> dict[str, Any]:
    candidate = row.get("candidate") or {}
    return candidate.get("risk_multipliers") or {}


def _risk_on_tagged(row: dict[str, Any]) -> bool:
    return any("risk_on" in str(key) for key in _risk_multipliers(row))


def _trade_quality(row: dict[str, Any]) -> float:
    candidate = row.get("candidate") or {}
    try:
        return float(candidate.get("trade_quality_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _target_mult(row: dict[str, Any]) -> float:
    candidate = row.get("candidate") or {}
    try:
        return float(candidate.get("target_mult_used") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _available_slots(row: dict[str, Any]) -> int:
    candidate = row.get("candidate") or {}
    try:
        return int(candidate.get("available_slots_at_entry_loop") or 99)
    except (TypeError, ValueError):
        return 99


def _condition_gates() -> dict[str, Condition]:
    return {
        "all_identity": lambda row: True,
        "trend_long_only": lambda row: row.get("strategy") == "trend_long",
        "breakout_long_only": lambda row: row.get("strategy") == "breakout_long",
        "not_risk_on_tagged": lambda row: not _risk_on_tagged(row),
        "risk_on_tagged": _risk_on_tagged,
        "available_slots_lte_3": lambda row: _available_slots(row) <= 3,
        "trade_quality_gte_0_95": lambda row: _trade_quality(row) >= 0.95,
        "trade_quality_lt_0_95": lambda row: _trade_quality(row) < 0.95,
        "target_mult_gte_6": lambda row: _target_mult(row) >= 6.0,
    }


def _max_consecutive_losses(rows: list[dict[str, Any]]) -> int:
    max_losses = 0
    current = 0
    for row in sorted(rows, key=lambda item: (item.get("exit_date") or "", item.get("ticker") or "")):
        if _money(row.get("pnl")) < 0:
            current += 1
            max_losses = max(max_losses, current)
        else:
            current = 0
    return max_losses


def _max_drawdown(rows: list[dict[str, Any]]) -> float:
    equity = STARTING_CAPITAL
    peak = STARTING_CAPITAL
    max_dd = 0.0
    for row in sorted(rows, key=lambda item: (item.get("exit_date") or "", item.get("ticker") or "")):
        equity += _money(row.get("pnl"))
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return round(max_dd, 6)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "pnl": 0.0, "wins": 0, "losses": 0}
    )
    by_ticker: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"trade_count": 0, "pnl": 0.0, "wins": 0, "losses": 0, "windows": set()}
    )
    total_pnl = 0.0
    wins = 0
    worst = None
    for row in rows:
        pnl = _money(row.get("pnl"))
        ret = row.get("net_return_pct")
        total_pnl += pnl
        wins += 1 if pnl > 0 else 0
        if isinstance(ret, (int, float)):
            worst = ret if worst is None else min(worst, ret)
        window = str(row.get("window") or "unknown")
        ticker = str(row.get("ticker") or "unknown")
        by_window[window]["trade_count"] += 1
        by_window[window]["pnl"] = round(by_window[window]["pnl"] + pnl, 2)
        by_window[window]["wins"] += 1 if pnl > 0 else 0
        by_window[window]["losses"] += 1 if pnl <= 0 else 0
        by_ticker[ticker]["trade_count"] += 1
        by_ticker[ticker]["pnl"] = round(by_ticker[ticker]["pnl"] + pnl, 2)
        by_ticker[ticker]["wins"] += 1 if pnl > 0 else 0
        by_ticker[ticker]["losses"] += 1 if pnl <= 0 else 0
        by_ticker[ticker]["windows"].add(window)

    for row in by_window.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
    for row in by_ticker.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["windows"] = sorted(row["windows"])

    positive_windows = [
        label for label, row in by_window.items() if float(row.get("pnl") or 0.0) > 0
    ]
    return {
        "trade_count": len(rows),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_pnl / STARTING_CAPITAL, 6),
        "wins": wins,
        "win_rate": round(wins / len(rows), 4) if rows else None,
        "worst_trade_pct": _round(worst),
        "max_drawdown_pct": _max_drawdown(rows),
        "max_consecutive_losses": _max_consecutive_losses(rows),
        "windows": sorted(by_window),
        "positive_windows": sorted(positive_windows),
        "windows_positive_count": len(positive_windows),
        "by_window": dict(sorted(by_window.items())),
        "by_ticker": dict(sorted(by_ticker.items())),
    }


def _summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: _summarize([row for row in rows if predicate(row)])
        for name, predicate in _condition_gates().items()
    }


def _passes_gate(summary: dict[str, Any], identity: dict[str, Any]) -> bool:
    identity_pnl = float(identity.get("total_pnl") or 0.0)
    pnl_floor = identity_pnl * (1.0 - MAX_AGGREGATE_PNL_HAIRCUT_VS_IDENTITY)
    return bool(
        summary.get("trade_count", 0) >= MIN_TRADE_COUNT
        and summary.get("total_pnl", 0.0) > 0
        and summary.get("windows_positive_count", 0) >= MIN_POSITIVE_WINDOWS
        and (summary.get("worst_trade_pct") or 0.0) > MAX_ACCEPTABLE_WORST_TRADE
        and summary.get("total_pnl", 0.0) >= pnl_floor
    )


def _select(summaries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    identity = summaries["all_identity"]
    accepted = []
    for name, summary in summaries.items():
        if name == "all_identity":
            continue
        if _passes_gate(summary, identity):
            accepted.append((float(summary["total_pnl"]), name, summary))
    accepted.sort(reverse=True)
    best_name = accepted[0][1] if accepted else None
    best = accepted[0][2] if accepted else None
    return {
        "identity_summary": identity,
        "selected_gate": best_name,
        "selected_summary": best,
        "condition_gate_passed": best_name is not None,
        "all_passing_gates": [name for _, name, _ in accepted],
        "live_short_promotable": False,
        "live_short_rejected_reason": (
            "This is still historical fixed-window evidence only; it ignores "
            "borrow/locate costs and lacks the forward CORE_MISFIT_PAPER "
            "closed-outcome gate required before live shorting."
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Gate | Trades | PnL | Win rate | Positive windows | Worst trade | Max DD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["condition_gate_summaries"].items():
        rows.append(
            "| {name} | {trades} | ${pnl:,.2f} | {win:.2%} | {wins} | {worst:.2%} | {dd:.2%} |".format(
                name=name,
                trades=row["trade_count"],
                pnl=row["total_pnl"],
                win=float(row.get("win_rate") or 0.0),
                wins=row["windows_positive_count"],
                worst=float(row.get("worst_trade_pct") or 0.0),
                dd=float(row.get("max_drawdown_pct") or 0.0),
            )
        )
    selected = payload["selection"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core Misfit Conditioned Short Shadow",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Fixed short policy is locked to `fixed_10d`; this experiment only sweeps production-visible condition gates.",
            "",
            *rows,
            "",
            f"Selected gate: `{selected['selected_gate']}`.",
            f"Condition gate passed: `{selected['condition_gate_passed']}`.",
            f"Live short promotable: `{selected['live_short_promotable']}`.",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = base.REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        base.REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


def run() -> dict[str, Any]:
    short_payload, misfit_payload = _load_payloads()
    rows = _joined_rows(short_payload, misfit_payload)
    summaries = _summaries(rows)
    selection = _select(summaries)
    decision = (
        "promising_replay_only_conditioned_short_shadow_not_live_promotable"
        if selection["condition_gate_passed"]
        else "rejected_conditioned_short_shadow"
    )
    selected_gate = selection["selected_gate"]
    interpretation = (
        f"The fixed-10d inverse edge becomes less window-fragile under the "
        f"`{selected_gate}` gate, but it remains replay-only and too sample-thin "
        "for live shorting."
        if selected_gate
        else "No production-visible condition gate fixed the short-shadow window fragility."
    )
    baseline_metrics = misfit_payload["gate1"]["baseline_metrics"]
    baseline_aggregate = misfit_payload["gate1"]["baseline_aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The core-misfit fixed-10d short shadow failed because returns were "
            "window-concentrated. A production-visible condition gate may remove "
            "the fragile subset while preserving most inverse PnL."
        ),
        "change_type": "short_shadow_condition_gate",
        "changed_variable": "short_condition_gate",
        "single_causal_variable": (
            "The short exit policy is locked to fixed_10d; only the condition "
            "gate selecting which already-observed core-misfit inverse signals "
            "are counted is swept."
        ),
        "parameters": {
            "source_short_artifact": str(SHORT_ARTIFACT.relative_to(base.REPO_ROOT)),
            "source_misfit_artifact": str(MISFIT_ARTIFACT.relative_to(base.REPO_ROOT)),
            "target_tickers": list(PRIMARY_MISFIT_TICKERS),
            "locked_short_policy": LOCKED_SHORT_POLICY,
            "condition_gates": list(_condition_gates()),
            "min_trade_count": MIN_TRADE_COUNT,
            "min_positive_windows": MIN_POSITIVE_WINDOWS,
            "max_aggregate_pnl_haircut_vs_identity": (
                MAX_AGGREGATE_PNL_HAIRCUT_VS_IDENTITY
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit/risk allocation: inverse value may be conditional on a "
                "production-visible source-signal state, not a blanket short rule."
            ),
            "2_history_check": {
                "exp-20260517-003": (
                    "Fixed-10d short made money but was positive in only one "
                    "window, so blanket short was rejected."
                ),
                "exp-20260517-002": (
                    "CORE_MISFIT_PAPER forward gate remains required before live shorting."
                ),
            },
            "3_single_causal_variable": "short_condition_gate",
            "4_acceptance_standard": (
                "Replay-only condition gate passes if a non-identity gate keeps "
                ">=4 trades, positive aggregate PnL, >=2 positive windows, "
                "worst trade > -10%, and loses no more than 20% of identity PnL."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_019_core_misfit_conditioned_short_shadow.py"
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-window signal artifact "
                "from exp-20260516-043 plus exp-20260517-003 fixed_10d short "
                "outcomes; no core replay metrics are changed"
            ),
            "locked_short_policy": LOCKED_SHORT_POLICY,
        },
        "gate1": {
            "baseline_metrics": baseline_metrics,
            "baseline_aggregate": baseline_aggregate,
        },
        "gate2": {
            "passed": bool(rows),
            "runtime_fields": [
                "fixed_10d short outcomes",
                "ticker",
                "window",
                "signal_date",
                "strategy",
                "candidate risk_multipliers",
                "candidate trade_quality_score",
                "candidate target_mult_used",
                "candidate available_slots_at_entry_loop",
            ],
            "joined_row_count": len(rows),
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_baseline_survival_rate": baseline_aggregate["survival_rate_min"],
            "passed": baseline_aggregate["survival_rate_min"] >= 0.05,
        },
        "gate4": {
            "passed": selection["condition_gate_passed"],
            "selected_gate": selected_gate,
            "selected_summary": selection["selected_summary"],
            "identity_summary": selection["identity_summary"],
            "all_passing_gates": selection["all_passing_gates"],
            "live_short_promotable": selection["live_short_promotable"],
            "live_short_rejected_reason": selection["live_short_rejected_reason"],
        },
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "delta_metrics": {
            "core_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "condition_gate_summaries": summaries,
        "selection": selection,
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "live_short_enabled": False,
        },
        "known_risks": [
            "The selected gate is still based on only a handful of historical signals.",
            "The mid_weak improvement can be driven by a single small TSM trade.",
            "Borrow, locate, buy-in, and hard-to-borrow costs remain unmodelled.",
            "This cannot override the CORE_MISFIT_PAPER forward closed-outcome gate.",
        ],
        "interpretation": interpretation,
        "rejection_reason": (
            None
            if selection["condition_gate_passed"]
            else "No non-identity production-visible gate passed the replay-only condition gate."
        ),
        "next_evidence_needed": (
            "Keep CORE_MISFIT_PAPER forward collection active; do not build a "
            "live short adapter unless the same condition remains positive on "
            ">=20 closed forward 10-day outcomes with borrow/locate modelling."
        ),
        "why_not_other_changes": (
            "No live short adapter, no core exclusion, no ticker expansion, and "
            "no new exit policy were added; the fixed_10d short policy from "
            "exp-20260517-003 remains locked."
        ),
        "related_files": [
            "quant/experiments/exp_20260518_019_core_misfit_conditioned_short_shadow.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }


if __name__ == "__main__":
    result = run()
    _persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "selected_gate": result["selection"]["selected_gate"],
                "condition_gate_passed": result["selection"]["condition_gate_passed"],
                "live_short_promotable": result["selection"]["live_short_promotable"],
                "selected_total_pnl": (
                    result["selection"]["selected_summary"] or {}
                ).get("total_pnl"),
                "selected_positive_windows": (
                    result["selection"]["selected_summary"] or {}
                ).get("positive_windows"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
