"""exp-20260509-013 state-surface sector-complement stack.

Alpha search, replay-only. Tests whether the late-window risk in the
event-state plus state-surface stack is caused by redundant sector exposure.

Single causal variable:
    For the state-surface satellite only, skip candidates whose sector is
    already represented by an active core A/B trade on the candidate entry date.

This does not change production orders, core A/B behavior, event source rules,
state-surface scoring, hold days, notional, LLM/news behavior, exits, sizing,
or live/default adapters. If a future version is promoted, the same active-core
sector context must be implemented in a shared run.py/backtester.py adapter with
parity tests.
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
from experiments import exp_20260509_012_event_state_plus_surface_stack as full_stack  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import _delta  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260509-013"
STEM = "state_surface_sector_complement"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


BEST_EVENT_VARIANT = full_stack.BEST_EVENT_VARIANT


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


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle_compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    needle_pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [
        line
        for line in lines
        if needle_compact not in line and needle_pretty not in line
    ]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _sector_for_ticker(ticker: Any) -> str:
    return str(SECTOR_MAP.get(str(ticker or "").upper(), "Unknown"))


def _with_sector(row: dict[str, Any]) -> dict[str, Any]:
    existing = str(row.get("sector") or "")
    if existing and existing not in {"Unknown", "snapshot_universe"}:
        return row
    return {**row, "sector": _sector_for_ticker(row.get("ticker"))}


def _active_core_positions(result: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker") or "").upper()
        out.append(
            {
                "ticker": ticker,
                "sector": str(trade.get("sector") or _sector_for_ticker(ticker)),
                "entry_date": str(trade.get("entry_date") or ""),
                "exit_date": str(trade.get("exit_date") or ""),
            }
        )
    return out


def _filter_sector_complement(
    candidates: list[dict[str, Any]],
    active_core: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept = []
    skipped = []
    for raw in candidates:
        row = _with_sector(raw)
        entry_date = str(row.get("entry_date") or "")
        sector = str(row.get("sector") or "Unknown")
        overlaps = [
            position
            for position in active_core
            if sector != "Unknown"
            and position.get("sector") == sector
            and str(position.get("entry_date") or "") <= entry_date <= str(position.get("exit_date") or "")
        ]
        if overlaps:
            skipped.append(
                {
                    **row,
                    "reason": "core_same_sector_active",
                    "active_core_tickers": sorted(
                        {str(position.get("ticker") or "").upper() for position in overlaps}
                    ),
                }
            )
        else:
            kept.append(row)
    return kept, skipped


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict(
        (label, _delta(before[label], after[label])) for label in event_base.WINDOWS
    )
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
    by_ticker: defaultdict[str, float] = defaultdict(float)
    total_positive = 0.0
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl <= 0:
            continue
        total_positive += pnl
        by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    if total_positive <= 0 or not by_ticker:
        return None
    return round(max(by_ticker.values()) / total_positive, 4)


def _surface_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    return surface_base._surface_summary(trades)


def _sector_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        sector = str(trade.get("sector") or _sector_for_ticker(trade.get("ticker")))
        row = out.setdefault(sector, {"trade_count": 0, "wins": 0, "total_pnl": 0.0})
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["total_pnl"] += pnl
    for row in out.values():
        count = int(row["trade_count"])
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["total_pnl"] = round(float(row["total_pnl"]), 2)
    return out


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": trade.get("ticker"),
            "sector": trade.get("sector") or _sector_for_ticker(trade.get("ticker")),
            "surface": trade.get("surface"),
            "decision_date": trade.get("decision_date"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "rank": trade.get("rank"),
            "score": trade.get("score"),
            "pnl": trade.get("pnl"),
            "net_return_pct": trade.get("net_return_pct"),
        }
        for trade in trades
    ]


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = event_base._load_event_trades()
    enriched_event_trades = event_base._enrich_event_trades(raw_event_trades)
    event_variant = event_base.VARIANTS[BEST_EVENT_VARIANT]

    event_state_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_stack_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sector_complement_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_sector_trades: list[dict[str, Any]] = []

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
        event_state_metrics[label] = event_base._combined_metrics(result, event_curve, event_trades)

        candidates = surface_base._raw_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
        candidates_with_sector = [_with_sector(row) for row in candidates]
        full_selected, full_skipped = surface_base._select_trades(candidates_with_sector)
        full_stack_trades = event_trades + full_selected
        full_stack_curve = event_base._event_equity_curve(
            full_stack_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        full_stack_metrics[label] = event_base._combined_metrics(result, full_stack_curve, full_stack_trades)

        sector_candidates, sector_gate_skipped = _filter_sector_complement(
            candidates,
            _active_core_positions(result),
        )
        sector_selected, sector_select_skipped = surface_base._select_trades(sector_candidates)
        sector_stack_trades = event_trades + sector_selected
        sector_stack_curve = event_base._event_equity_curve(
            sector_stack_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        sector_complement_metrics[label] = event_base._combined_metrics(
            result,
            sector_stack_curve,
            sector_stack_trades,
        )
        all_sector_trades.extend({**trade, "window": label} for trade in sector_selected)

        surface_sleeve[label] = {
            "raw_candidate_count": len(candidates),
            "price_ready_candidate_count": sum(1 for row in candidates if row.get("status") == "price_ready"),
            "full_stack_selected_trade_count": len(full_selected),
            "sector_complement_selected_trade_count": len(sector_selected),
            "sector_gate_skipped_price_ready_count": sum(
                1 for row in sector_gate_skipped if row.get("status") == "price_ready"
            ),
            "full_stack_selected_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in full_selected), 2),
            "sector_complement_selected_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in sector_selected),
                2,
            ),
            "full_stack_surface_summary": _surface_summary(full_selected),
            "sector_complement_surface_summary": _surface_summary(sector_selected),
            "sector_complement_sector_summary": _sector_summary(sector_selected),
            "full_stack_selected_trades": _selected_trade_rows(full_selected),
            "sector_complement_selected_trades": _selected_trade_rows(sector_selected),
            "skipped_reason_counts": dict(
                Counter(
                    str(row.get("reason") or row.get("status") or "unknown")
                    for row in [*sector_gate_skipped, *sector_select_skipped, *full_skipped]
                )
            ),
        }

    vs_event_state = _aggregate_delta(event_state_metrics, sector_complement_metrics)
    vs_full_stack = _aggregate_delta(full_stack_metrics, sector_complement_metrics)

    gate4_vs_event_state = (
        vs_event_state["windows_ev_improved"] == 3
        and (
            (vs_event_state["aggregate_ev_delta_pct"] or 0.0) > 0.10
            or (vs_event_state["aggregate_pnl_delta_pct"] or 0.0) > 0.05
        )
    )
    gate4_vs_full_stack = (
        vs_full_stack["windows_ev_improved"] == 3
        and (
            (vs_full_stack["aggregate_ev_delta_pct"] or 0.0) > 0.10
            or (vs_full_stack["aggregate_pnl_delta_pct"] or 0.0) > 0.05
        )
    )
    decision = "rejected_full_stack_replacement"
    rationale = (
        "Rejected as a replacement for exp-20260509-012. The same-sector "
        "complement gate fixes the late_strong EV regression and remains "
        "positive versus event-state-only, but it gives back too much aggregate "
        "EV and PnL versus the full stack, mainly by skipping high-value old_thin "
        "Technology candidates."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "event_state_surface_stack_complementarity",
        "alpha_hypothesis_category": "candidate_pool_allocation",
        "alpha_hypothesis": (
            "The state-surface satellite should add replacement value when it "
            "contributes sector-orthogonal exposure to the existing A/B core; "
            "same-sector overlap may explain the late_strong stack risk."
        ),
        "hypothesis": (
            "Apply the frozen state-surface satellite only when the candidate "
            "sector is not already represented by an active core A/B trade on "
            "the candidate entry date."
        ),
        "change_type": "replay_only_state_surface_complementarity_gate",
        "single_causal_variable": "skip state-surface satellite candidates with active core same-sector exposure",
        "parameters": {
            "event_variant": BEST_EVENT_VARIANT,
            "state_surface_policy": "frozen exp-20260509-010 mechanics",
            "sector_complement_gate": "candidate_sector not in active_core_ab_sectors_on_entry_date",
            "locked_variables": [
                "core A/B signal generation",
                "event source definitions",
                "event state-surface add-on scalar",
                "state-surface scoring",
                "state-surface max candidates",
                "state-surface max active positions",
                "state-surface notional",
                "state-surface hold days",
                "LLM/news replay",
                "sizing",
                "exits",
                "universe",
            ],
        },
        "history_guardrails": {
            "checked_experiment_log": True,
            "checked_mechanism_insights": True,
            "not_repeated_failures": [
                "Not a state-surface surface allowlist or balanced-surface prune.",
                "Not a top-N, hold-day, notional, event-source, or state-score-floor retune.",
                "Not a ticker-level core-overlap exclusion from exp-20260509-011.",
                "Not an event/state shared-capacity priority retry.",
            ],
            "why_this_retry_is_valid": (
                "exp-20260509-012 explicitly left an orthogonal risk discriminator "
                "as the valid next step for the late_strong risk flag. Sector "
                "complementarity is ex-ante, production-observable, and different "
                "from surface subset pruning."
            ),
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in event_base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in event_base.WINDOWS.items()
        },
        "before_metrics": {
            "event_state_addon": event_state_metrics,
            "full_stack_exp_20260509_012": full_stack_metrics,
        },
        "after_metrics": sector_complement_metrics,
        "delta_metrics": {
            "vs_event_state_addon": vs_event_state,
            "vs_full_stack_exp_20260509_012": vs_full_stack,
        },
        "expected_value_score_delta": {
            "vs_event_state_addon": vs_event_state["aggregate_ev_delta"],
            "vs_full_stack_exp_20260509_012": vs_full_stack["aggregate_ev_delta"],
        },
        "gate4": {
            "primary_baseline": "full_stack_exp_20260509_012",
            "passed_vs_event_state_addon": gate4_vs_event_state,
            "passed_vs_full_stack_exp_20260509_012": gate4_vs_full_stack,
            "reason_primary": (
                "The experiment modifies the exp-20260509-012 full stack, so "
                "the full stack is the correct marginal baseline. It fails that "
                "comparison despite being positive versus event-state-only."
            ),
            "single_ticker_positive_share": _single_ticker_positive_share(all_sector_trades),
        },
        "surface_sleeve": surface_sleeve,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "LLM soft-ranking remains sample-limited; this alpha test uses "
                "fully replayable OHLCV/core-position sector context."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_positive": (
                "Implement active-core sector context in a shared adapter consumed "
                "by run.py and backtester.py, then add parity tests before any "
                "live/default orders."
            ),
        },
        "decision_rationale": rationale,
        "rejection_reason": (
            "Fails the correct marginal comparison against the full exp-20260509-012 "
            "stack: aggregate EV and PnL both regress, with EV improving in only "
            "late_strong versus the full stack."
        ),
        "next_action": (
            "Do not promote or repeat same-sector complement gating. Keep the "
            "event-state add-on and full state-surface stack as separate paper "
            "leads until forward replacement outcomes or a different late-risk "
            "discriminator appears."
        ),
        "risk_of_change": (
            "The gate may remove the exact same-sector continuation winners that "
            "make the state-surface sleeve valuable in older/weaker windows."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking, earnings/revisions, platform RS20, 10-K "
            "scouts, event-source retunes, state-score floors, add-on heat, and "
            "surface subsets because recent logs mark them data-limited, rejected, "
            "or not the current marginal bottleneck."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-013 State-Surface Sector Complement",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Tests whether the state-surface satellite should avoid sectors already represented by active core A/B trades.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Event-State EV | Full Stack EV | Sector-Complement EV | vs Event EV | vs Full EV | vs Full PnL | vs Full Sharpe | vs Full DD | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in event_base.WINDOWS:
        event_metrics = payload["before_metrics"]["event_state_addon"][label]
        full_metrics = payload["before_metrics"]["full_stack_exp_20260509_012"][label]
        after = payload["after_metrics"][label]
        vs_event = payload["delta_metrics"]["vs_event_state_addon"]["by_window"][label]
        vs_full = payload["delta_metrics"]["vs_full_stack_exp_20260509_012"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {event_ev:.4f} | {full_ev:.4f} | {after_ev:.4f} | "
            "{vs_event_ev:+.4f} | {vs_full_ev:+.4f} | ${vs_full_pnl:+,.2f} | "
            "{vs_full_sharpe:+.2f} | {vs_full_dd:+.2%} | {trades} |".format(
                label=label,
                event_ev=event_metrics["expected_value_score"],
                full_ev=full_metrics["expected_value_score"],
                after_ev=after["expected_value_score"],
                vs_event_ev=vs_event["expected_value_score"],
                vs_full_ev=vs_full["expected_value_score"],
                vs_full_pnl=vs_full["total_pnl"],
                vs_full_sharpe=vs_full["sharpe_daily"],
                vs_full_dd=vs_full["max_drawdown_pct"],
                trades=sleeve["sector_complement_selected_trade_count"],
            )
        )
    vs_event = payload["delta_metrics"]["vs_event_state_addon"]
    vs_full = payload["delta_metrics"]["vs_full_stack_exp_20260509_012"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "- Versus event-state add-on: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_event["aggregate_ev_delta"],
                vs_event["aggregate_ev_delta_pct"] or 0.0,
                vs_event["aggregate_pnl_delta"],
                vs_event["aggregate_pnl_delta_pct"] or 0.0,
                vs_event["windows_ev_improved"],
                vs_event["windows_ev_regressed"],
            ),
            "- Versus full exp-20260509-012 stack: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_full["aggregate_ev_delta"],
                vs_full["aggregate_ev_delta_pct"] or 0.0,
                vs_full["aggregate_pnl_delta"],
                vs_full["aggregate_pnl_delta_pct"] or 0.0,
                vs_full["windows_ev_improved"],
                vs_full["windows_ev_regressed"],
            ),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, exits, or adapters changed. A positive version would require a shared run.py/backtester.py adapter and parity tests.",
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
            "title": "Reject state-surface sector-complement gate",
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
    _append_jsonl_dedup(EXPERIMENT_LOG, compact)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "vs_event_state_addon": payload["delta_metrics"]["vs_event_state_addon"],
                    "vs_full_stack_exp_20260509_012": payload["delta_metrics"][
                        "vs_full_stack_exp_20260509_012"
                    ],
                    "gate4": payload["gate4"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
