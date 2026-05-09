"""exp-20260509-011 state-surface core-overlap filter replay.

Alpha search, replay-only. The current state-surface satellite is a promising
candidate-pool extension, but it should be tested as replacement-value alpha
rather than assumed useful when it repeats the same tickers already selected by
core A/B. This experiment changes one variable: exclude state-surface sleeve
candidates whose ticker is already traded by core trend/breakout in the same
canonical window.

Core A/B entries, ranking, sizing, exits, add-ons, universe, LLM/news behavior,
state-surface scoring, top-N, hold days, and notional are locked.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260507_016_state_surface_satellite_replay as base  # noqa: E402


EXPERIMENT_ID = "exp-20260509-011"
STEM = "state_surface_core_overlap_filter"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)

CORE_STRATEGIES = {"trend_long", "breakout_long"}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(base._safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _core_tickers(result: dict[str, Any]) -> set[str]:
    return {
        str(trade.get("ticker") or "").upper()
        for trade in result.get("trades") or []
        if trade.get("strategy") in CORE_STRATEGIES and trade.get("ticker")
    }


def _filter_core_overlap_candidates(
    candidates: list[dict[str, Any]],
    core_tickers: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for row in candidates:
        ticker = str(row.get("ticker") or "").upper()
        if ticker in core_tickers:
            dropped.append(
                {
                    **row,
                    "reason": "same_window_core_ticker",
                    "core_overlap_filter": True,
                }
            )
        else:
            kept.append(row)
    return kept, dropped


def _selected_summary(
    *,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "raw_candidate_count": len(candidates),
        "price_ready_candidate_count": sum(
            1 for row in candidates if row.get("status") == "price_ready"
        ),
        "selected_trade_count": len(selected),
        "selected_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in selected),
            2,
        ),
        "selected_win_rate": round(
            sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0)
            / len(selected),
            4,
        )
        if selected
        else None,
        "surface_summary": base._surface_summary(selected),
        "skipped_reason_counts": dict(
            Counter(str(row.get("reason") or "unknown") for row in skipped)
        ),
        "selected_trades": [
            {
                "ticker": trade.get("ticker"),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "score": trade.get("score"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
            for trade in selected
        ],
    }


def _drop_summary(dropped: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "dropped_candidate_count": len(dropped),
        "price_ready_dropped_count": sum(
            1 for row in dropped if row.get("status") == "price_ready"
        ),
        "reason_counts": dict(
            Counter(str(row.get("reason") or "unknown") for row in dropped)
        ),
        "sample": [
            {
                "ticker": row.get("ticker"),
                "date": row.get("date") or row.get("decision_date"),
                "surface": row.get("surface"),
                "rank": row.get("rank"),
                "score": row.get("score"),
                "status": row.get("status"),
            }
            for row in dropped[:25]
        ],
    }


def _material_gate(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    delta: dict[str, Any],
) -> dict[str, Any]:
    gate4_by_window = OrderedDict(
        (label, base._gate4(before[label], after[label])) for label in base.WINDOWS
    )
    material = (
        (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
        or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
        or any(row["passes_sharpe"] for row in gate4_by_window.values())
        or any(row["passes_drawdown"] for row in gate4_by_window.values())
    )
    passed = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and bool(material)
    )
    return {
        "by_window": gate4_by_window,
        "material": bool(material),
        "passed": bool(passed),
        "rule": (
            "Incremental acceptance requires >=2 windows EV improvement, zero EV "
            "regressions versus the full state-surface sleeve, and one Gate 4 "
            "materiality trigger."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-011 State-Surface Core-Overlap Filter",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Tests whether the state-surface sleeve should avoid tickers already traded by core A/B in the same canonical window.",
        "",
        "## Three-Window Result Versus Full State-Surface Sleeve",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Before sleeve trades | After sleeve trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        full = payload["full_state_surface_sleeve"][label]
        filtered = payload["filtered_state_surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {btrades} | {atrades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                btrades=full["selected_trade_count"],
                atrades=filtered["selected_trade_count"],
            )
        )
    agg = payload["delta_metrics"]
    lines.extend(
        [
            "",
            "## Aggregate Gate",
            "",
            "- EV sum: {:.4f} -> {:.4f} ({:+.4f}, {:+.2%})".format(
                agg["baseline_ev_sum"],
                agg["after_ev_sum"],
                agg["aggregate_ev_delta"],
                agg["aggregate_ev_delta_pct"] or 0.0,
            ),
            "- PnL sum: ${:,.2f} -> ${:,.2f} ({:+,.2f}, {:+.2%})".format(
                agg["baseline_pnl_sum"],
                agg["after_pnl_sum"],
                agg["aggregate_pnl_delta"],
                agg["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- EV windows improved/regressed: {}/{}".format(
                agg["windows_ev_improved"],
                agg["windows_ev_regressed"],
            ),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Dropped Candidate Summary",
            "",
            "```json",
            json.dumps(payload["core_overlap_drop_summary"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "No live/default orders, core A/B behavior, LLM, news, default backtest strategy, or production adapter changed. Any positive trade-enabled version must be implemented through shared run/backtester policy with parity tests.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = base._load_price_map()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    filtered_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    drop_summary: dict[str, dict[str, Any]] = OrderedDict()
    core_ticker_summary: dict[str, Any] = OrderedDict()

    for label, window in base.WINDOWS.items():
        result = base._load_core_result(window)
        tickers = _core_tickers(result)
        candidates = base._raw_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
        full_selected, full_skipped = base._select_trades(candidates)
        filtered_candidates, dropped = _filter_core_overlap_candidates(candidates, tickers)
        filtered_selected, filtered_skipped = base._select_trades(filtered_candidates)

        full_curve = base._event_equity_curve(
            full_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        filtered_curve = base._event_equity_curve(
            filtered_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        core_metrics[label] = base._core_metrics(result)
        before_metrics[label] = base._combined_metrics(result, full_curve, full_selected)
        after_metrics[label] = base._combined_metrics(result, filtered_curve, filtered_selected)
        full_sleeve[label] = _selected_summary(
            candidates=candidates,
            selected=full_selected,
            skipped=full_skipped,
        )
        filtered_sleeve[label] = _selected_summary(
            candidates=filtered_candidates,
            selected=filtered_selected,
            skipped=filtered_skipped,
        )
        drop_summary[label] = _drop_summary(dropped)
        core_ticker_summary[label] = {
            "core_ticker_count": len(tickers),
            "core_tickers": sorted(tickers),
        }

    delta = base._aggregate_delta(before_metrics, after_metrics)
    gate = _material_gate(before_metrics, after_metrics, delta)
    accepted = bool(gate["passed"])
    if accepted:
        decision = "promising_replay_only_core_overlap_filter"
        decision_rationale = (
            "Promising replay-only: excluding same-window core A/B tickers improved "
            "the full state-surface sleeve under the pre-registered three-window "
            "incremental Gate 4 standard. Do not promote to live/default orders "
            "without shared policy and parity tests."
        )
        rejection_reason = None
        next_action = (
            "Design a shared default-off state-surface candidate policy that can "
            "expose same-window core ticker overlap in both run.py and backtester.py."
        )
    else:
        decision = "rejected_core_overlap_filter"
        decision_rationale = (
            "Rejected: excluding same-window core A/B tickers did not improve the "
            "full state-surface sleeve with enough three-window stability and "
            "materiality. The current result says duplicate core ticker exposure "
            "is not the main state-surface weakness."
        )
        rejection_reason = decision_rationale
        next_action = (
            "Do not retry same-window core ticker exclusion on this frozen "
            "state-surface sample; a valid retry needs forward replacement-value "
            "outcomes or a materially different discriminator."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "state_surface_core_overlap_filter_replay",
        "mechanism_family": "state_aware_candidate_pool_extension",
        "hypothesis": (
            "If state-surface sleeve alpha is mostly incremental candidate-pool "
            "replacement value, then removing tickers already traded by core A/B "
            "in the same canonical window should preserve or improve the sleeve."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension",
            "entry_exit_ranking_or_allocation": "satellite entry/allocation",
            "why_this_now": (
                "LLM soft-ranking and earnings/revisions are data-limited, event "
                "bundle tuning is already the strongest replay lead but awaits "
                "forward evidence, and the state-surface sleeve needs an "
                "orthogonal discriminator rather than surface/top-N/hold retunes."
            ),
        },
        "single_causal_variable": (
            "state-surface candidate eligibility by same-window core A/B ticker overlap"
        ),
        "parameters": {
            "acceptance_baseline": "full_state_surface_sleeve",
            "core_overlap_definition": "ticker appears in any trend_long or breakout_long trade in the same canonical window",
            "daily_candidate_count": base.DAILY_CANDIDATE_COUNT,
            "max_active_surface_positions": base.MAX_ACTIVE_SURFACE_POSITIONS,
            "hold_days": base.HOLD_DAYS,
            "event_notional_usd": base.EVENT_NOTIONAL,
            "round_trip_cost_pct": base.ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "state-surface scoring",
                "state-surface surfaces",
                "top-N candidate count",
                "max active sleeve positions",
                "hold days",
                "notional",
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "LLM/news replay",
                "event bundle",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in base.WINDOWS.items()
        },
        "historical_experiment_check": {
            "checked_sources": [
                "AGENTS.md",
                "docs/alpha-optimization-playbook.md",
                "docs/backtesting.md",
                "docs/experiments/logs/exp-20260509-010.json",
                "docs/experiments/artifacts/exp-20260509-010_state_surface_current_stack_revalidation.md",
                "docs/experiments/logs/exp-20260509-002.json",
            ],
            "recent_no_go_or_blocked_surfaces": [
                "Do not rerun full state-surface revalidation",
                "Do not drop balanced_state_leadership again",
                "Do not sweep nearby top-N, hold-day, notional, or max-active parameters",
                "Do not retune event-bundle sources/notional/hold days",
                "Do not use LLM soft-ranking until outcome joins exist",
            ],
            "mechanism_insight_conflict": (
                "No conflict: this is a core-overlap replacement-value test, not a "
                "surface prune, nearby score threshold, top-N/capacity sweep, or "
                "event bundle overlap retry."
            ),
            "why_not_simple_repeat": (
                "Event core-overlap filtering was rejected for the event bundle, "
                "but this tests a different state-surface candidate-pool sleeve "
                "whose stated weakness is possible overlap with core momentum "
                "leaders."
            ),
        },
        "core_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4": gate,
        "core_ticker_summary": core_ticker_summary,
        "full_state_surface_sleeve": full_sleeve,
        "filtered_state_surface_sleeve": filtered_sleeve,
        "core_overlap_drop_summary": drop_summary,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in base.WINDOWS
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "default_backtest_strategy_changed": False,
            "production_order_path_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "LLM soft-ranking outcome joins remain sparse; this run searches "
                "a deterministic non-LLM candidate-pool alpha instead."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": (
            "I skipped LLM ranking, earnings revisions, event notional/source "
            "retunes, balanced-surface deletion, top-N/hold-day sweeps, and "
            "raw universe growth because recent records mark them data-limited, "
            "rejected, or too close to prior no-go zones."
        ),
        "risk_of_change": (
            "Filtering core-overlap tickers may remove confirmation alpha where "
            "state-surface and A/B independently agree on the same winner."
        ),
        "next_action": next_action,
        "next_retry_requires": [
            "Do not retry same-window core ticker exclusion on this frozen sample.",
            "A valid retry needs forward paper replacement-value outcomes or a materially different discriminator.",
            "Any positive promotion must use shared run/backtester policy with parity tests.",
        ],
        "experiment_log_jsonl_note": (
            "Not appended by this run because docs/experiment_log.jsonl has "
            "pre-existing unstaged automation changes; canonical record is the "
            "docs/experiments log file and artifact."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface core-overlap filter",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "delta_metrics": payload["delta_metrics"],
                    "gate4": payload["gate4"],
                    "production_impact": payload["production_impact"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
