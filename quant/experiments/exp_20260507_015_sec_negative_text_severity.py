"""exp-20260507-015 SEC negative text-severity replay.

Alpha search, replay only. The accepted evidence says the default-off event
bundle is currently the strongest external alpha family, but recent source
pruning and timing/notional/capacity variants are no-go. This tests one
different discriminator inside the SEC negative-reaction source: whether severe
negative filing text marks real deterioration rather than tradable overreaction.

The primary variant leaves governance/procedural events unchanged and removes
only SEC negative-reaction trades with language_score < -6 or
negative_phrase_hits > 8. No core signal, ranking, sizing, exit, LLM, news,
production order, event source, notional, capacity, or holding-period code is
changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    WINDOWS,
    _aggregate_delta,
    _combined_metrics,
    _core_metrics,
    _event_equity_curve,
    _gate4,
    _load_core_result,
    _load_event_trades,
    _source_summary,
    _write_json,
    _write_text,
)


EXP_ID = "exp-20260507-015"
PRIMARY_VARIANT = "exclude_severe_sec_negative_text"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "sec_negative_text_severity.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / "exp-20260507-015_sec_negative_text_severity.md"
)


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _is_sec_negative(trade: dict[str, Any]) -> bool:
    return str(trade.get("source") or "") == "sec_negative_reaction"


def _is_severe_sec_negative_text(trade: dict[str, Any]) -> bool:
    language_score = _num(trade.get("language_score"))
    negative_hits = _num(trade.get("negative_phrase_hits"))
    if language_score is None or negative_hits is None:
        return True
    return language_score < -6 or negative_hits > 8


def _passes_primary_gate(trade: dict[str, Any]) -> bool:
    if not _is_sec_negative(trade):
        return True
    return not _is_severe_sec_negative_text(trade)


def _field_audit(event_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [
        trade
        for trades in event_trades_by_window.values()
        for trade in trades
        if _is_sec_negative(trade)
    ]
    missing_language = [
        trade for trade in rows if _num(trade.get("language_score")) is None
    ]
    missing_hits = [
        trade for trade in rows if _num(trade.get("negative_phrase_hits")) is None
    ]
    return {
        "sec_negative_selected_trades": len(rows),
        "language_score_present": len(rows) - len(missing_language),
        "negative_phrase_hits_present": len(rows) - len(missing_hits),
        "missing_language_examples": [
            {
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
            }
            for trade in missing_language[:5]
        ],
        "missing_negative_phrase_hit_examples": [
            {
                "ticker": trade.get("ticker"),
                "entry_date": trade.get("entry_date"),
            }
            for trade in missing_hits[:5]
        ],
    }


def _severity_cohort_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    cohorts: dict[str, dict[str, Any]] = OrderedDict(
        [
            ("non_sec_negative_event", {"trade_count": 0, "wins": 0, "total_pnl": 0.0}),
            ("sec_negative_non_severe_text", {"trade_count": 0, "wins": 0, "total_pnl": 0.0}),
            ("sec_negative_severe_text", {"trade_count": 0, "wins": 0, "total_pnl": 0.0}),
        ]
    )
    for trade in trades:
        if not _is_sec_negative(trade):
            key = "non_sec_negative_event"
        elif _is_severe_sec_negative_text(trade):
            key = "sec_negative_severe_text"
        else:
            key = "sec_negative_non_severe_text"
        row = cohorts[key]
        pnl = float(trade.get("pnl") or 0.0)
        row["trade_count"] += 1
        row["wins"] += int(pnl > 0)
        row["total_pnl"] += pnl
    for row in cohorts.values():
        count = row["trade_count"]
        row["win_rate"] = round(row["wins"] / count, 4) if count else None
        row["total_pnl"] = round(row["total_pnl"], 2)
    return cohorts


def _removed_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    removed = [trade for trade in trades if not _passes_primary_gate(trade)]
    return [
        {
            "source": trade.get("source"),
            "ticker": trade.get("ticker"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "pnl": trade.get("pnl"),
            "net_return_pct": trade.get("net_return_pct"),
            "language_score": trade.get("language_score"),
            "negative_phrase_hits": trade.get("negative_phrase_hits"),
            "reaction_excess_return": trade.get("reaction_excess_return"),
        }
        for trade in removed
    ]


def _delta_alias(delta: dict[str, Any]) -> dict[str, Any]:
    return {
        "before_ev_sum": delta["baseline_ev_sum"],
        "after_ev_sum": delta["after_ev_sum"],
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_ev_delta_pct": delta["aggregate_ev_delta_pct"],
        "before_pnl_sum": delta["baseline_pnl_sum"],
        "after_pnl_sum": delta["after_pnl_sum"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "aggregate_pnl_delta_pct": delta["aggregate_pnl_delta_pct"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "windows_pnl_improved": delta["windows_pnl_improved"],
        "windows_pnl_regressed": delta["windows_pnl_regressed"],
        "by_window": delta["by_window"],
    }


def _passes_vs_full(
    full_metrics: dict[str, dict[str, Any]],
    variant_metrics: dict[str, dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    delta = _aggregate_delta(full_metrics, variant_metrics)
    gate4_by_window = OrderedDict(
        (label, _gate4(full_metrics[label], variant_metrics[label]))
        for label in WINDOWS
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
        and material
    )
    return passed, {
        "by_window": gate4_by_window,
        "delta": _delta_alias(delta),
        "passed": passed,
        "rule": (
            "Primary severity gate must improve EV in at least two canonical "
            "windows, regress EV in zero windows, and clear one Gate 4 materiality trigger."
        ),
    }


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-015 SEC Negative Text Severity",
        "",
        "Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, event notional, capacity, holding period, and production orders are unchanged.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-window comparison",
        "",
        "| Window | Core EV | Full bundle EV | Severity-gated EV | Delta vs full | Core PnL | Full PnL | Severity PnL | Removed trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        core = payload["core_metrics"][label]
        full = payload["full_bundle_metrics"][label]
        variant = payload["variant_metrics"][PRIMARY_VARIANT][label]
        delta = payload["severity_vs_full"]["delta"]["by_window"][label]
        removed_count = len(payload["variant_event_overlay"][PRIMARY_VARIANT][label]["removed_trades"])
        lines.append(
            "| {label} | {core_ev:.4f} | {full_ev:.4f} | {var_ev:.4f} | {delta_ev:.4f} | ${core_pnl:,.2f} | ${full_pnl:,.2f} | ${var_pnl:,.2f} | {removed} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                full_ev=full["expected_value_score"],
                var_ev=variant["expected_value_score"],
                delta_ev=delta["expected_value_score"],
                core_pnl=core["total_pnl"],
                full_pnl=full["total_pnl"],
                var_pnl=variant["total_pnl"],
                removed=removed_count,
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Removed Trades",
            "",
            "```json",
            json.dumps(
                {
                    label: payload["variant_event_overlay"][PRIMARY_VARIANT][label]["removed_trades"]
                    for label in WINDOWS
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
        ]
    )
    _write_text(AUDIT_MD, "\n".join(lines))


def main() -> int:
    event_trades_by_window, coverage, prices = _load_event_trades()
    field_audit = _field_audit(event_trades_by_window)
    if field_audit["language_score_present"] != field_audit["sec_negative_selected_trades"]:
        raise RuntimeError("language_score missing on selected SEC negative trades")
    if field_audit["negative_phrase_hits_present"] != field_audit["sec_negative_selected_trades"]:
        raise RuntimeError("negative_phrase_hits missing on selected SEC negative trades")

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_bundle_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = {
        PRIMARY_VARIANT: OrderedDict(),
    }
    variant_event_overlay: dict[str, dict[str, Any]] = {
        PRIMARY_VARIANT: OrderedDict(),
    }
    full_event_overlay: dict[str, dict[str, Any]] = OrderedDict()
    severity_cohorts: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        all_trades = event_trades_by_window[label]
        gated_trades = [trade for trade in all_trades if _passes_primary_gate(trade)]

        full_event_curve = _event_equity_curve(
            all_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        gated_event_curve = _event_equity_curve(
            gated_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )

        core_metrics[label] = _core_metrics(result)
        full_bundle_metrics[label] = _combined_metrics(result, full_event_curve, all_trades)
        variant_metrics[PRIMARY_VARIANT][label] = _combined_metrics(
            result,
            gated_event_curve,
            gated_trades,
        )
        severity_cohorts[label] = _severity_cohort_summary(all_trades)
        full_event_overlay[label] = {
            "event_trade_count": len(all_trades),
            "event_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in all_trades), 2),
            "source_summary": _source_summary(all_trades),
        }
        variant_event_overlay[PRIMARY_VARIANT][label] = {
            "event_trade_count": len(gated_trades),
            "event_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in gated_trades), 2),
            "source_summary": _source_summary(gated_trades),
            "removed_trades": _removed_trade_rows(all_trades),
            "removed_reason_counts": dict(
                Counter(
                    "language_score_lt_minus_6_or_negative_phrase_hits_gt_8"
                    for trade in all_trades
                    if not _passes_primary_gate(trade)
                )
            ),
        }

    full_vs_core = _delta_alias(_aggregate_delta(core_metrics, full_bundle_metrics))
    severity_passed, severity_vs_full = _passes_vs_full(
        full_bundle_metrics,
        variant_metrics[PRIMARY_VARIANT],
    )
    decision = "promising_replay_only" if severity_passed else "rejected"
    decision_rationale = (
        "Promising replay-only: the SEC negative text-severity gate improved the frozen full event bundle across the required windows. It is not production-promoted here; a shared event policy and forward paper evidence would still be required."
        if severity_passed
        else "Rejected: severe negative SEC filing text did not improve the full event bundle. Do not retry simple language_score/negative_phrase_hits exclusion gates on this frozen sample; the evidence says the market-reaction event packet is stronger than this text-severity subfilter."
    )

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_quality_replay_filter",
        "mechanism_family": "sec_negative_reaction_text_severity",
        "hypothesis": (
            "Within the frozen SEC negative-reaction event sleeve, severe negative filing text may indicate real business deterioration rather than temporary overreaction; excluding that subset may improve satellite event alpha."
        ),
        "alpha_hypothesis": {
            "category": "entry / event-quality filtering",
            "why_this_not_llm": "LLM soft-ranking data remains sparse; this uses replayable SEC filing text fields already present on selected event trades.",
            "why_not_candidate_pool_expansion": "Recent OHLCV/news shadow-universe candidates had late-window weakness and snapshot membership limits; this tests a covered event-quality discriminator instead of adding noisy tickers.",
        },
        "single_causal_variable": "exclude severe SEC negative-reaction text within the frozen full event bundle",
        "parameters": {
            "primary_variant": PRIMARY_VARIANT,
            "excluded_source": "sec_negative_reaction only",
            "language_score_min": -6,
            "negative_phrase_hits_max": 8,
            "event_notional_usd": EVENT_NOTIONAL,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "event sources",
                "event notional",
                "event capacity",
                "event holding period",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "history_guardrails": {
            "similar_experiments_checked": {
                "exp-20260504-007": "Broad positive SEC filing language underperformed; this tests the already-selected SEC negative-reaction sleeve only.",
                "exp-20260504-039": "Governance/procedural cells accepted replay-only; this leaves those cells unchanged.",
                "exp-20260505-031": "Followthrough delay was rejected; this does not change timing.",
                "exp-20260507-012": "Source pruning was rejected; this does not remove a whole event source or rerun source subsets.",
            },
            "mechanism_no_go_check": [
                "No event source composition change.",
                "No reaction-bucket threshold change.",
                "No notional, capacity, holding-period, or timing change.",
                "No production promotion from same-sample event evidence.",
            ],
            "why_not_simple_repeat": (
                "The tested discriminator is filing text severity inside an already-frozen event packet, not another source, notional, capacity, holding-period, or reaction-threshold sweep."
            ),
        },
        "field_audit": field_audit,
        "coverage": coverage,
        "core_metrics": core_metrics,
        "full_bundle_metrics": full_bundle_metrics,
        "variant_metrics": variant_metrics,
        "full_vs_core": full_vs_core,
        "severity_vs_full": severity_vs_full,
        "expected_value_score_delta": {
            "full_bundle_vs_core": {
                label: full_vs_core["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
            "severity_gate_vs_full": {
                label: severity_vs_full["delta"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "full_event_overlay": full_event_overlay,
        "variant_event_overlay": variant_event_overlay,
        "severity_cohort_summary": severity_cohorts,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": "This does not blame or remove LLM; it avoids the current LLM replay sample limit by testing deterministic SEC text fields.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "promotion_blocker_if_accepted": "Would require shared event-sleeve policy plus run/backtester adapters before live use.",
        },
        "risk_of_change": (
            "A severity exclusion can remove profitable capitulation/overreaction trades, especially when negative filing text is already priced into the first reaction."
        ),
        "why_not_other_attractive_points": [
            "LLM soft-ranking is still sample-limited, so this run avoids it instead of blocking alpha search.",
            "Event source pruning was just rejected, so this does not drop a source.",
            "Broad breadth/dispersion and core runner exit variants were recently rejected or accepted; this leaves core allocation and exits unchanged.",
            "Universe expansion scouts remain snapshot-limited and weak in late_strong; this does not add noisy tickers.",
        ],
        "decision_rationale": decision_rationale,
        "rejection_reason": None if severity_passed else "no stable EV improvement versus the full frozen event bundle",
        "next_action": (
            "If continuing event alpha, prefer new forward outcomes or materially new event metadata; do not retry simple SEC negative text-severity exclusion gates on this sample."
        ),
        "related_files": [
            "quant/experiments/exp_20260507_015_sec_negative_text_severity.py",
            "data/experiments/exp-20260507-015/sec_negative_text_severity.json",
            "experiments/logs/exp-20260507-015.json",
            "experiments/tickets/exp-20260507-015.json",
            "experiments/artifacts/exp-20260507-015_sec_negative_text_severity.md",
        ],
    }

    ticket = {
        "experiment_id": EXP_ID,
        "title": "SEC negative text-severity gate",
        "status": decision,
        "summary": decision_rationale,
        "next_action": payload["next_action"],
        "related_files": payload["related_files"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_report(payload)

    print(json.dumps({
        "experiment_id": EXP_ID,
        "decision": decision,
        "full_bundle_vs_core_ev_delta_sum": full_vs_core["aggregate_ev_delta"],
        "severity_gate_vs_full_ev_delta_sum": severity_vs_full["delta"]["aggregate_ev_delta"],
        "severity_gate_vs_full_pnl_delta": severity_vs_full["delta"]["aggregate_pnl_delta"],
        "removed_trades": {
            label: len(variant_event_overlay[PRIMARY_VARIANT][label]["removed_trades"])
            for label in WINDOWS
        },
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
