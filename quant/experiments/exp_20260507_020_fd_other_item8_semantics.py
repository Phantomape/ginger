"""exp-20260507-020 FD/Other item-code semantic discriminator.

Alpha search. Prior FD/Other negative-reaction events were positive but too
small to justify another production-visible source. This tests one richer,
pre-registered semantic discriminator: keep only SEC 8-K item 8.01 "Other
Events" packets and exclude item 7.01 FD packets. Core A/B logic, event
notional, hold period, capacity, reaction bucket, LLM, news, and production
orders stay unchanged.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments.exp_20260504_037_sec_fd_other_event_sleeve import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    MAX_EVENT_POSITIONS,
    ROUND_TRIP_COST_PCT,
    TARGET_CATEGORY,
    TARGET_REACTION_BUCKET,
    WINDOWS,
    _candidate_events,
    _combined_metrics,
    _core_metrics,
    _delta,
    _event_curve,
    _gate4,
    _select_trades,
)


EXP_ID = "exp-20260507-020"
STEM = "fd_other_item8_semantics"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"
ARTIFACT_MD = REPO_ROOT / "docs" / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _item_codes(row: dict[str, Any]) -> set[str]:
    return {str(code) for code in row.get("eight_k_item_codes") or []}


def _is_item8_other_event(row: dict[str, Any]) -> bool:
    codes = _item_codes(row)
    return "8.01" in codes and "7.01" not in codes


def _item_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    by_cell: Counter[str] = Counter()
    for row in rows:
        codes = tuple(sorted(_item_codes(row)))
        counter.update(codes)
        by_cell["+".join(codes) if codes else "missing"] += 1
    return {
        "item_code_counts": dict(counter.most_common()),
        "item_code_mix_counts": dict(by_cell.most_common()),
    }


def _load_core_result(window: dict[str, str]) -> dict[str, Any]:
    result = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _delta(before[label], after[label])) for label in WINDOWS)
    baseline_ev = sum(float(before[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    after_ev = sum(float(after[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    baseline_pnl = sum(float(before[label]["total_pnl"] or 0.0) for label in WINDOWS)
    after_pnl = sum(float(after[label]["total_pnl"] or 0.0) for label in WINDOWS)
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - baseline_ev) / baseline_ev, 6)
        if baseline_ev
        else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - baseline_pnl) / baseline_pnl, 6)
        if baseline_pnl
        else None,
        "windows_ev_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0.0)
            > (before[label].get("expected_value_score") or 0.0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0.0)
            < (before[label].get("expected_value_score") or 0.0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0.0) > (before[label].get("total_pnl") or 0.0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0.0) < (before[label].get("total_pnl") or 0.0)
        ),
    }


def _full_source_comparison(
    all_candidates: list[dict[str, Any]],
    item8_candidates: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    out: dict[str, Any] = OrderedDict()
    for label, window in WINDOWS.items():
        full_selected, _ = _select_trades(
            all_candidates,
            prices,
            start=window["start"],
            end=window["end"],
        )
        item8_selected, _ = _select_trades(
            item8_candidates,
            prices,
            start=window["start"],
            end=window["end"],
        )
        full_pnl = round(sum(float(row.get("pnl") or 0.0) for row in full_selected), 2)
        item8_pnl = round(sum(float(row.get("pnl") or 0.0) for row in item8_selected), 2)
        out[label] = {
            "full_fd_other_selected_count": len(full_selected),
            "full_fd_other_event_pnl": full_pnl,
            "item8_selected_count": len(item8_selected),
            "item8_event_pnl": item8_pnl,
            "event_pnl_delta_vs_full_fd_other": round(item8_pnl - full_pnl, 2),
            "removed_selected_trades": [
                {
                    "ticker": row.get("ticker"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get("exit_date"),
                    "pnl": row.get("pnl"),
                    "eight_k_item_codes": row.get("eight_k_item_codes"),
                }
                for row in full_selected
                if not _is_item8_other_event(row)
            ],
        }
    return out


def _event_trade_summary(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trades = [
        trade
        for payload in rows.values()
        for trade in payload["selected_trades"]
    ]
    total_pnl = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
    wins = sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0)
    by_ticker: Counter[str] = Counter()
    for trade in trades:
        by_ticker[str(trade.get("ticker") or "").upper()] += abs(float(trade.get("pnl") or 0.0))
    total_abs = sum(by_ticker.values())
    top = by_ticker.most_common(1)[0] if by_ticker else (None, 0.0)
    return {
        "trade_count": len(trades),
        "total_pnl": total_pnl,
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "top_abs_trade_concentration": {
            "ticker": top[0],
            "abs_pnl": round(top[1], 2),
            "share_of_abs_pnl": round(top[1] / total_abs, 4) if total_abs else None,
        },
        "by_window": {
            label: {
                "trade_count": rows[label]["selected_trade_count"],
                "event_pnl": rows[label]["event_pnl"],
                "win_rate": rows[label]["event_win_rate"],
            }
            for label in WINDOWS
        },
    }


def _gate4_summary(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, _gate4(before[label], after[label])) for label in WINDOWS)
    material_windows = sum(
        1
        for row in by_window.values()
        if row["passes_material_ev"]
        or row["passes_pnl"]
        or row["passes_sharpe"]
        or row["passes_drawdown"]
    )
    return {
        "rule": (
            "EV first. Require majority-window EV improvement, zero EV regression, "
            "and at least one material Gate 4 trigger before considering promotion."
        ),
        "by_window": by_window,
        "material_windows": material_windows,
    }


def _decision(delta: dict[str, Any], gate4: dict[str, Any]) -> tuple[str, str, str | None]:
    positive_stable = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and delta["aggregate_ev_delta"] > 0
    )
    material = (
        (delta["aggregate_ev_delta_pct"] or 0.0) > 0.10
        or (delta["aggregate_pnl_delta_pct"] or 0.0) > 0.05
        or gate4["material_windows"] >= 2
    )
    if positive_stable and material:
        return (
            "accepted_requires_forward_queue_review",
            "Accepted for follow-up only: item 8.01 FD/Other semantics improved the canonical windows materially, but production use still requires shared default-off queue evidence.",
            None,
        )
    if positive_stable:
        reason = (
            "Positive but below materiality: item 8.01 semantics improved the "
            "FD/Other source directionally without enough Gate 4 lift."
        )
        return "rejected_positive_immaterial", reason, reason
    reason = (
        "Rejected: item 8.01 semantics did not improve the canonical windows "
        "stably enough to justify another event-source complexity layer."
    )
    return "rejected", reason, reason


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-020 FD/Other Item 8.01 Semantics",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Event trades | Event PnL | Full-source PnL delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        event = payload["event_details"][label]
        full = payload["full_source_comparison"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${epnl:+,.2f} | ${fd:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=event["selected_trade_count"],
                epnl=event["event_pnl"],
                fd=full["event_pnl_delta_vs_full_fd_other"],
            )
        )
    agg = payload["delta_metrics"]
    summary = payload["event_trade_summary"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Aggregate EV delta: `{agg['aggregate_ev_delta']:+.4f}` ({agg['aggregate_ev_delta_pct']:+.2%})",
            f"- Aggregate PnL delta: `${agg['aggregate_pnl_delta']:+,.2f}` ({agg['aggregate_pnl_delta_pct']:+.2%})",
            f"- EV windows improved/regressed: `{agg['windows_ev_improved']}` / `{agg['windows_ev_regressed']}`",
            f"- Event trades/PnL/win rate: `{summary['trade_count']}` / `${summary['total_pnl']:+,.2f}` / `{summary['win_rate']}`",
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "No production universe, ranking, sizing, exits, LLM, news, or order path changed.",
            "",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines))


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = {
        "experiment_id": EXP_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": {
            label: payload["delta_metrics"]["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        },
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
    }
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXP_ID}"' not in line
            and f'"experiment_id": "{EXP_ID}"' not in line
        ]
    lines.append(json.dumps(_safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    all_candidates, prices = _candidate_events()
    item8_candidates = [row for row in all_candidates if _is_item8_other_event(row)]

    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    event_details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        print(f"[{label}] core baseline + item8 FD/Other replay")
        result = _load_core_result(window)
        selected, skipped = _select_trades(
            item8_candidates,
            prices,
            start=window["start"],
            end=window["end"],
        )
        curve = _event_curve(selected, prices, start=window["start"], end=window["end"])
        before_metrics[label] = _core_metrics(result)
        after_metrics[label] = _combined_metrics(result, curve, selected)
        wins = sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0)
        event_details[label] = {
            "candidate_count": sum(
                1 for row in item8_candidates if window["start"] <= str(row.get("entry_date") or "") <= window["end"]
            ),
            "selected_trade_count": len(selected),
            "skipped_count": len(skipped),
            "skip_reasons": dict(Counter(str(row.get("reason") or "unknown") for row in skipped)),
            "event_pnl": round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
            "event_win_rate": round(wins / len(selected), 4) if selected else None,
            "selected_trades": selected,
            "skipped_candidates": skipped,
        }

    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4 = _gate4_summary(before_metrics, after_metrics)
    decision, rationale, rejection_reason = _decision(delta, gate4)
    status = decision

    payload: dict[str, Any] = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "event_semantic_quality_discriminator",
        "mechanism_family": "sec_fd_other_event_item8_semantics",
        "hypothesis": (
            "Within the FD/Other negative-reaction SEC sleeve, item 8.01 "
            "Other Events may be a cleaner temporary-uncertainty alpha than "
            "item 7.01 FD/context packets. Keeping item 8.01 while excluding "
            "7.01 should improve event-source quality without changing "
            "reaction thresholds, holding period, notional, or core A/B logic."
        ),
        "alpha_hypothesis": {
            "category": "entry/event-source quality",
            "why_this_now": (
                "The full FD/Other source was directionally positive but too "
                "small for promotion; the playbook's valid retry condition is "
                "structured semantics that changes event quality, not another "
                "source-composition, notional, hold, or threshold sweep."
            ),
        },
        "historical_experiment_check": {
            "similar_experiments": {
                "exp-20260504-037": "FD/Other negative-reaction sleeve positive but below materiality.",
                "exp-20260505-004": "Adding full FD/Other as a fourth event-bundle source was positive but immaterial.",
                "exp-20260504-039": "SEC governance/procedural fixed semantic sleeve accepted for follow-up; not this FD/Other family.",
                "exp-20260507-012": "Event-bundle source pruning failed; this is within-source semantics, not source pruning.",
                "exp-20260507-019": "Event+state shared-capacity allocation rejected; no capacity/priority change here.",
            },
            "mechanism_insight_check": (
                "This does not touch the current do-not-repeat zones: no LLM "
                "soft-ranking, no event-source composition, no reaction bucket "
                "retune, no event notional/cap/hold sweep, no live promotion, "
                "and no state-surface combination."
            ),
            "why_not_simple_repeat": (
                "The causal variable is item-code semantics inside a fixed "
                "FD/Other branch. It is not rerunning the full branch, adding "
                "the fourth bundle source, or mining a nearby reaction threshold."
            ),
        },
        "parameters": {
            "single_causal_variable": "FD/Other branch requires 8-K item 8.01 and excludes 7.01",
            "filing_category": TARGET_CATEGORY,
            "reaction_bucket": TARGET_REACTION_BUCKET,
            "semantic_filter": {"require_item": "8.01", "exclude_item": "7.01"},
            "hold_days": HOLD_DAYS,
            "event_notional_usd": EVENT_NOTIONAL,
            "max_event_positions": MAX_EVENT_POSITIONS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core A/B universe",
                "core signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "reaction bucket",
                "event notional",
                "hold days",
                "event capacity",
                "production orders",
            ],
        },
        "date_range": {label: f"{window['start']} -> {window['end']}" for label, window in WINDOWS.items()},
        "market_regime_summary": {label: window["state_note"] for label, window in WINDOWS.items()},
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4": gate4,
        "coverage": {
            "full_fd_other_candidate_count": len(all_candidates),
            "item8_candidate_count": len(item8_candidates),
            "removed_by_semantic_filter_count": len(all_candidates) - len(item8_candidates),
            "full_fd_other_item_summary": _item_summary(all_candidates),
            "item8_item_summary": _item_summary(item8_candidates),
        },
        "full_source_comparison": _full_source_comparison(all_candidates, item8_candidates, prices),
        "event_details": event_details,
        "event_trade_summary": _event_trade_summary(event_details),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
            "promotion_blocker_if_positive": (
                "A shared default-off event queue / paper adapter with forward "
                "replacement-value outcomes is required before production use."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM soft-ranking outcome joins remain sparse; this tests deterministic SEC semantics.",
        },
        "decision_rationale": rationale,
        "rejection_reason": rejection_reason,
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still sample-limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "event_source_composition": "Rejected by exp-20260507-012 and exp-20260505-004.",
            "state_surface_combination": "Rejected by exp-20260507-019.",
            "raw_universe_expansion": "Recent guardrails reject broad/noisy ticker growth.",
        },
        "risk_of_change": (
            "The semantic filter may overfit sparse 8-K item-code samples and "
            "remove valid FD/context winners; promotion needs forward paper evidence."
        ),
        "next_action": (
            "Do not promote from frozen-sample replay alone. If positive, let "
            "FD/Other item-code semantics accumulate default-off forward paper "
            "outcomes; if rejected, avoid nearby FD/Other item-code filters "
            "without new samples."
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
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "FD/Other item 8.01 semantics",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
        },
    )
    _write_report(payload)
    _append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "delta_metrics": payload["delta_metrics"],
                    "coverage": payload["coverage"],
                    "event_trade_summary": payload["event_trade_summary"],
                    "full_source_comparison": payload["full_source_comparison"],
                    "gate4": payload["gate4"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
