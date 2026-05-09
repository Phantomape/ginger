"""exp-20260509-012 event-state add-on plus state-surface stack.

Alpha search, replay-only. Tests whether the two strongest frozen paper
candidate-pool leads remain additive on the current stack:

1. exp-20260509-007 non-generic positive event state add-on.
2. exp-20260509-010 state-surface satellite sleeve.

No production strategy code, live/default orders, core A/B ranking, sizing,
exits, add-ons, LLM, news, event source rules, or sleeve mechanics are changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260507_016_state_surface_satellite_replay as surface_base  # noqa: E402
from experiments import exp_20260507_026_non_generic_event_state_addon as event_base  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import _delta, _gate4  # noqa: E402


EXPERIMENT_ID = "exp-20260509-012"
STEM = "event_state_plus_surface_stack"
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
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BEST_EVENT_VARIANT = "non_generic_positive_add_200"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _delta(before[label], after[label])) for label in event_base.WINDOWS)
    baseline_ev = sum(float(before[label].get("expected_value_score") or 0.0) for label in event_base.WINDOWS)
    after_ev = sum(float(after[label].get("expected_value_score") or 0.0) for label in event_base.WINDOWS)
    baseline_pnl = sum(float(before[label].get("total_pnl") or 0.0) for label in event_base.WINDOWS)
    after_pnl = sum(float(after[label].get("total_pnl") or 0.0) for label in event_base.WINDOWS)
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - baseline_ev) / baseline_ev, 6) if baseline_ev else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - baseline_pnl) / baseline_pnl, 6) if baseline_pnl else None,
        "windows_ev_improved": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("expected_value_score") or 0)
            > (before[label].get("expected_value_score") or 0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("expected_value_score") or 0)
            < (before[label].get("expected_value_score") or 0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("total_pnl") or 0) > (before[label].get("total_pnl") or 0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("total_pnl") or 0) < (before[label].get("total_pnl") or 0)
        ),
    }


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for trade in positive:
        by_ticker[str(trade.get("ticker") or "").upper()] += float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 4) if by_ticker else None


def _overlap_summary(
    event_trades: list[dict[str, Any]],
    surface_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    event_entry_keys = {
        (str(trade.get("ticker") or "").upper(), str(trade.get("entry_date") or ""))
        for trade in event_trades
    }
    surface_entry_keys = {
        (str(trade.get("ticker") or "").upper(), str(trade.get("entry_date") or ""))
        for trade in surface_trades
    }

    active_pairs: list[dict[str, Any]] = []
    for event_trade in event_trades:
        ticker = str(event_trade.get("ticker") or "").upper()
        event_entry = str(event_trade.get("entry_date") or "")
        event_exit = str(event_trade.get("exit_date") or "")
        for surface_trade in surface_trades:
            if str(surface_trade.get("ticker") or "").upper() != ticker:
                continue
            surface_entry = str(surface_trade.get("entry_date") or "")
            surface_exit = str(surface_trade.get("exit_date") or "")
            if event_entry <= surface_exit and surface_entry <= event_exit:
                active_pairs.append(
                    {
                        "ticker": ticker,
                        "event_entry_date": event_entry,
                        "event_exit_date": event_exit,
                        "surface_entry_date": surface_entry,
                        "surface_exit_date": surface_exit,
                    }
                )

    surface_by_source = Counter(str(trade.get("surface") or "unknown") for trade in surface_trades)
    return {
        "same_ticker_same_entry_count": len(event_entry_keys & surface_entry_keys),
        "same_ticker_active_overlap_count": len(active_pairs),
        "same_ticker_active_overlaps": active_pairs,
        "surface_trade_count_by_surface": dict(surface_by_source),
    }


def _surface_sleeve_summary(
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "raw_candidate_count": len(candidates),
        "price_ready_candidate_count": sum(1 for row in candidates if row.get("status") == "price_ready"),
        "selected_trade_count": len(selected),
        "selected_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in selected), 2),
        "selected_win_rate": round(
            sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0) / len(selected),
            4,
        )
        if selected
        else None,
        "surface_summary": surface_base._surface_summary(selected),
        "skipped_reason_counts": dict(Counter(str(row.get("reason") or "unknown") for row in skipped)),
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


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = event_base._load_event_trades()
    enriched_event_trades = event_base._enrich_event_trades(raw_event_trades)
    event_variant = event_base.VARIANTS[BEST_EVENT_VARIANT]

    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    event_selection: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    overlap: dict[str, dict[str, Any]] = OrderedDict()
    all_overlay_trades: list[dict[str, Any]] = []

    for label, window in event_base.WINDOWS.items():
        result = event_base._load_core_result(window)
        event_trades = [
            event_base._scaled_trade(trade, BEST_EVENT_VARIANT, event_variant)
            for trade in enriched_event_trades[label]
        ]
        event_curve = event_base._event_equity_curve(
            event_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = event_base._combined_metrics(result, event_curve, event_trades)

        candidates = surface_base._raw_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
        selected_surface_trades, skipped = surface_base._select_trades(candidates)
        stacked_trades = event_trades + selected_surface_trades
        stacked_curve = event_base._event_equity_curve(
            stacked_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_metrics[label] = event_base._combined_metrics(result, stacked_curve, stacked_trades)

        event_selection[label] = event_base._trade_summary(event_trades)
        surface_sleeve[label] = _surface_sleeve_summary(candidates, selected_surface_trades, skipped)
        overlap[label] = _overlap_summary(event_trades, selected_surface_trades)
        all_overlay_trades.extend(stacked_trades)

    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4_by_window = OrderedDict(
        (label, _gate4(before_metrics[label], after_metrics[label])) for label in event_base.WINDOWS
    )
    single_ticker_positive_share = _single_ticker_positive_share(all_overlay_trades)
    material = (
        (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
        or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
        or any(row["passes_sharpe"] for row in gate4_by_window.values())
        or any(row["passes_drawdown"] for row in gate4_by_window.values())
    )
    drawdown_cap_ok = all(float(after_metrics[label].get("max_drawdown_pct") or 0.0) <= 0.20 for label in event_base.WINDOWS)
    majority_ev_ok = delta["windows_ev_improved"] >= 2
    concentration_ok = single_ticker_positive_share is None or single_ticker_positive_share <= 0.50
    passed = bool(majority_ev_ok and material and drawdown_cap_ok and concentration_ok)
    late_risk_flag = delta["windows_ev_regressed"] > 0

    if passed:
        decision = "promising_replay_only_additive_stack_risk_flag"
        rationale = (
            "Promising only as a replay/forward-paper stack: adding the frozen "
            "state-surface sleeve to the frozen non-generic event state add-on "
            "improved aggregate EV and PnL, with EV improvement in the majority "
            "of canonical windows. It is not a live/default promotion because "
            "late_strong EV and Sharpe regressed while drawdown rose."
        )
        rejection_reason = None
        next_action = (
            "Keep the combined stack in default-off forward paper attribution. "
            "Do not route it to live/default orders until shared adapter parity "
            "and closed forward replacement-value evidence address the late_strong "
            "risk flag."
        )
    else:
        decision = "rejected"
        rationale = (
            "Rejected: the frozen state-surface sleeve did not add enough robust "
            "incremental value on top of the event state add-on after applying "
            "the three-window EV/materiality/drawdown/concentration guards."
        )
        rejection_reason = rationale
        next_action = (
            "Keep the event state add-on and state-surface sleeve separate in "
            "paper attribution; do not retry simple stack overlays without new "
            "forward evidence or an orthogonal risk discriminator."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "paper_sleeve_stack_replay",
        "mechanism_family": "candidate_pool_extension_stack",
        "hypothesis": (
            "The current strongest frozen event allocation lead and the strongest "
            "non-event state-surface candidate-pool lead may be additive because "
            "they select different opportunity surfaces."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension/allocation",
            "entry_exit_ranking_or_allocation": "allocation plus satellite entry",
            "why_this_now": (
                "LLM soft-ranking and earnings/revisions remain data-limited; "
                "nearby event source/notional, state-surface parameter, overlap, "
                "gap/reclaim, staged entry, and add-on reserve variants were "
                "recently rejected or marked no-repeat. The remaining high-value "
                "question is whether the two frozen positive sleeves are additive."
            ),
        },
        "single_causal_variable": (
            "Add the frozen state-surface satellite sleeve on top of the frozen "
            "non-generic positive event state add-on; every underlying sleeve "
            "definition stays locked."
        ),
        "parameters": {
            "event_baseline_variant": BEST_EVENT_VARIANT,
            "event_baseline_parent": "exp-20260509-007",
            "state_surface_parent": "exp-20260509-010",
            "surface_hold_days": surface_base.HOLD_DAYS,
            "surface_daily_candidate_count": surface_base.DAILY_CANDIDATE_COUNT,
            "surface_max_active_positions": surface_base.MAX_ACTIVE_SURFACE_POSITIONS,
            "event_source_definitions_changed": False,
            "event_notional_scalars_changed": False,
            "state_surface_sleeve_parameters_changed": False,
            "core_strategy_changed": False,
            "locked_variables": [
                "core A/B entries",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news decisions",
                "event source definitions",
                "event hold days",
                "event notional scalar",
                "state-surface top-N",
                "state-surface hold days",
                "state-surface capacity",
                "production order path",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}" for label, window in event_base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in event_base.WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "expected_value_score_delta": delta["aggregate_ev_delta"],
        "delta_metrics": delta,
        "gate4": {
            "passed": passed,
            "material": material,
            "majority_ev_ok": majority_ev_ok,
            "drawdown_cap_ok": drawdown_cap_ok,
            "concentration_ok": concentration_ok,
            "late_risk_flag": late_risk_flag,
            "single_ticker_positive_share": single_ticker_positive_share,
            "by_window": gate4_by_window,
            "rule": (
                "EV-first three-window gate against the event-state add-on baseline: "
                "require majority EV improvement, a Gate 4 materiality trigger, "
                "post-stack drawdown <= 20%, and single-ticker positive share <= 50%. "
                "Any EV-regressed window blocks production promotion even if replay-only "
                "aggregate evidence is positive."
            ),
        },
        "coverage": {
            "event_source_coverage": source_coverage,
            "event_trade_count": sum(int(event_selection[label]["trade_count"]) for label in event_base.WINDOWS),
            "surface_selected_trade_count": sum(
                int(surface_sleeve[label]["selected_trade_count"]) for label in event_base.WINDOWS
            ),
        },
        "event_selection": event_selection,
        "surface_sleeve": surface_sleeve,
        "overlap": overlap,
        "historical_experiment_check": {
            "direct_parents": {
                "exp-20260509-007": (
                    "Non-generic positive event state add-on is the strongest "
                    "current event-bundle allocation lead."
                ),
                "exp-20260509-010": (
                    "Frozen state-surface satellite remains the strongest "
                    "non-event candidate-pool lead on the current stack."
                ),
            },
            "explicit_no_repeat": {
                "exp-20260509-011": (
                    "Core-overlap exclusion was rejected; this run does not retry "
                    "or alter overlap filtering."
                ),
                "state-surface parameter sweeps": (
                    "Top-N, hold-day, notional, max-active-position, and dropping "
                    "balanced_state_leadership remain no-repeat on this sample."
                ),
                "event source/notional retunes": (
                    "Source pruning, broad state-score tilt, and nearby event "
                    "retunes remain no-repeat without forward evidence."
                ),
            },
            "mechanism_insight_conflict": (
                "No conflict: the run does not weaken LLM, add noisy tickers, "
                "retune thresholds, retry overlap exclusion, or promote a "
                "backtester-only production rule."
            ),
            "why_not_simple_repeat": (
                "This answers a new composition question: whether the two "
                "already-positive frozen paper sleeves are additive when measured "
                "against the stronger event-state add-on baseline."
            ),
        },
        "llm_metrics": {
            "llm_changed": False,
            "llm_replay_coverage_changed": False,
            "attribution_note": "No LLM prompt, boundary, veto, ranking, or logging behavior changed.",
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
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "parity_note": (
                "This is an explicit replay-only paper stack. Production/default "
                "orders are unchanged; promotion would require a shared "
                "run.py/backtester.py trade adapter and parity tests."
            ),
            "promotion_blocker_if_positive": (
                "The late_strong EV/Sharpe/drawdown risk flag plus missing shared "
                "adapter and forward closed replacement-value evidence block live "
                "or default-order promotion."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "next_action": next_action,
        "why_not_other_attractive_points": (
            "I skipped LLM ranking, earnings/revision ranking, universe expansion, "
            "event source pruning, state-surface parameter sweeps, overlap exclusion, "
            "gap/reclaim exits, staged entry, and generic add-on reserves because "
            "recent logs mark them data-limited, rejected, concentrated, or below "
            "materiality."
        ),
        "risk_of_change": (
            "The stack can compound exposure to momentum leadership; late_strong "
            "already shows lower Sharpe and higher drawdown despite higher PnL."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-012 Event-State Add-On Plus State-Surface Stack",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Tests whether the frozen state-surface satellite adds value on top of the frozen non-generic event state add-on.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Event EV | Stack EV | Delta EV | Event PnL | Stack PnL | Delta PnL | Sharpe Delta | DD Delta | Surface trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in event_base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dsh:+.2f} | {ddd:+.2%} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dsh=delta["sharpe_daily"],
                ddd=delta["max_drawdown_pct"],
                trades=sleeve["selected_trade_count"],
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
            "- PnL windows improved/regressed: {}/{}".format(
                agg["windows_pnl_improved"],
                agg["windows_pnl_regressed"],
            ),
            "- Single-ticker positive share: {}".format(
                payload["gate4"]["single_ticker_positive_share"]
            ),
            "- Late risk flag: `{}`".format(payload["gate4"]["late_risk_flag"]),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, or exits changed. A positive production version would require a shared run.py/backtester.py adapter and parity tests.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event-state plus state-surface stack",
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

    compact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "next_action": payload["next_action"],
        "risk_of_change": payload["risk_of_change"],
        "related_files": payload["related_files"],
    }
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(_safe({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
        "gate4": payload["gate4"],
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
