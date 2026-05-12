"""exp-20260511-104 post-news pre-event RS20 context.

Alpha search, replay-only. Test one event-quality variable inside the locked
PEAD-like post-news continuation surface from exp-20260509-020: whether
pre-event 20-trading-day relative strength versus SPY improves candidate
selection. Reaction threshold, volume threshold, hold period, notional,
capacity, core A/B policy, ranking, sizing, exits, and LLM/news replay stay
fixed.
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

from experiments import exp_20260509_020_post_news_continuation_entry_pattern as base  # noqa: E402


EXPERIMENT_ID = "exp-20260511-104"
STEM = "post_news_pre_event_rs20_context"
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
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = base.WINDOWS
LOOKBACK_DAYS = 20
VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "exclude_rs20_laggard_5pp",
            {
                "min_pre_event_rs20_excess": -0.05,
                "description": "Drop candidates lagging SPY by more than 5 pp before the event.",
            },
        ),
        (
            "rs20_positive_only",
            {
                "min_pre_event_rs20_excess": 0.0,
                "description": "Keep candidates whose pre-event 20d return beats SPY.",
            },
        ),
        (
            "rs20_leader_5pp_only",
            {
                "min_pre_event_rs20_excess": 0.05,
                "description": "Keep candidates beating SPY by at least the accepted RS20 5 pp threshold.",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
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


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return round(out, digits)


def _gate2_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"passed": False, "path": _repo_rel(path), "missing": "file"}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    positions = list(payload.get("positions") or []) + list(payload.get("observations") or [])
    missing = [
        row.get("ticker") or "<unknown>"
        for row in positions
        if not row.get("entry_date") or row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing,
        "path": _repo_rel(path),
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
    }


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date")): idx for idx, row in enumerate(rows or [])}


def _pre_event_rs20(
    ticker: str,
    event_date: str,
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker_rows = prices.get(str(ticker).upper()) or []
    spy_rows = prices.get("SPY") or []
    ticker_idx = _row_index(ticker_rows).get(event_date)
    spy_idx = _row_index(spy_rows).get(event_date)
    if ticker_idx is None or spy_idx is None:
        return {"status": "missing_event_date_price"}
    # Use the close before the event day so this tests trend context, not the
    # already-locked event-day reaction variable.
    end_ticker_idx = ticker_idx - 1
    end_spy_idx = spy_idx - 1
    start_ticker_idx = end_ticker_idx - LOOKBACK_DAYS
    start_spy_idx = end_spy_idx - LOOKBACK_DAYS
    if start_ticker_idx < 0 or start_spy_idx < 0:
        return {"status": "insufficient_pre_event_lookback"}
    try:
        ticker_start = float(ticker_rows[start_ticker_idx]["close"])
        ticker_end = float(ticker_rows[end_ticker_idx]["close"])
        spy_start = float(spy_rows[start_spy_idx]["close"])
        spy_end = float(spy_rows[end_spy_idx]["close"])
    except (KeyError, TypeError, ValueError):
        return {"status": "missing_pre_event_close"}
    if min(ticker_start, ticker_end, spy_start, spy_end) <= 0:
        return {"status": "invalid_pre_event_close"}
    ticker_ret20 = ticker_end / ticker_start - 1.0
    spy_ret20 = spy_end / spy_start - 1.0
    return {
        "status": "ready",
        "pre_event_ticker_ret20": ticker_ret20,
        "pre_event_spy_ret20": spy_ret20,
        "pre_event_rs20_excess": ticker_ret20 - spy_ret20,
    }


def _annotate_rs20(
    candidates: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for row in candidates:
        rs = _pre_event_rs20(str(row.get("ticker") or ""), str(row.get("event_date") or ""), prices)
        annotated.append(
            {
                **row,
                "pre_event_rs20_status": rs["status"],
                "pre_event_ticker_ret20": _round(rs.get("pre_event_ticker_ret20"), 6),
                "pre_event_spy_ret20": _round(rs.get("pre_event_spy_ret20"), 6),
                "pre_event_rs20_excess": _round(rs.get("pre_event_rs20_excess"), 6),
            }
        )
    return annotated


def _apply_rs20_gate(
    candidates: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    min_excess: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    gated_out: list[dict[str, Any]] = []
    for row in candidates:
        excess = row.get("pre_event_rs20_excess")
        if isinstance(excess, (int, float)) and float(excess) >= min_excess:
            kept.append(row)
            continue
        gated_out.append({**row, "status": "pre_event_rs20_rejected"})
    return kept, rejected + gated_out


def _rs20_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        float(row["pre_event_rs20_excess"])
        for row in rows
        if isinstance(row.get("pre_event_rs20_excess"), (int, float))
    ]
    if not values:
        return {"count": 0, "avg": None, "min": None, "max": None, "positive_rate": None}
    values_sorted = sorted(values)
    return {
        "count": len(values_sorted),
        "avg": _round(sum(values_sorted) / len(values_sorted), 6),
        "median": _round(values_sorted[len(values_sorted) // 2], 6),
        "min": _round(values_sorted[0], 6),
        "max": _round(values_sorted[-1], 6),
        "positive_rate": _round(sum(1 for value in values_sorted if value > 0) / len(values_sorted), 4),
    }


def _run_event_stack(
    *,
    prices: dict[str, list[dict[str, Any]]],
    core_results: dict[str, dict[str, Any]],
    core_metrics: dict[str, dict[str, Any]],
    variant: dict[str, Any] | None,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    shadow_metrics: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        candidates, rejected = base._build_candidates(
            prices,
            start=window["start"],
            end=window["end"],
        )
        candidates = _annotate_rs20(candidates, prices)
        qualified_before_gate = len(candidates)
        if variant is not None:
            candidates, rejected = _apply_rs20_gate(
                candidates,
                rejected,
                float(variant["min_pre_event_rs20_excess"]),
            )
        selected, capacity_skipped = base._select_trades(candidates)
        event_curve = base._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_metrics[label] = base._combined_metrics(
            core_results[label],
            event_curve,
            selected,
        )
        quality = base._candidate_quality(selected, rejected + capacity_skipped)
        shadow_metrics[label] = {
            "variant": variant or {"gate": "none"},
            "qualified_before_rs20_gate": qualified_before_gate,
            "qualified_after_rs20_gate": len(candidates),
            "selected_trade_count": len(selected),
            "capacity_skipped_count": len(capacity_skipped),
            "selected_pnl": round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
            "selected_win_rate": quality["selected_win_rate"],
            "selected_avg_event_reaction_pct": quality["selected_avg_event_reaction_pct"],
            "selected_avg_volume_ratio": quality["selected_avg_volume_ratio"],
            "selected_rs20_distribution": _rs20_distribution(selected),
            "qualified_rs20_distribution": _rs20_distribution(candidates),
            "selected_by_ticker": quality["selected_by_ticker"],
            "rejection_status_counts": quality["rejection_status_counts"],
            "selected_trades": selected,
        }

    return {
        "after_metrics": after_metrics,
        "delta_vs_core": base._aggregate_delta(core_metrics, after_metrics),
        "shadow_metrics": shadow_metrics,
    }


def _variant_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return base._aggregate_delta(before, after)


def _best_variant(variants: dict[str, dict[str, Any]]) -> str:
    return max(
        variants,
        key=lambda name: (
            variants[name]["delta_vs_raw_post_news"]["aggregate_ev_delta"],
            variants[name]["delta_vs_raw_post_news"]["aggregate_pnl_delta"],
            variants[name]["delta_vs_core"]["aggregate_ev_delta"],
        ),
    )


def _selected_trade_count(result: dict[str, Any]) -> int:
    return sum(
        int(row.get("selected_trade_count") or 0)
        for row in result.get("shadow_metrics", {}).values()
    )


def _gate4(best: dict[str, Any]) -> dict[str, Any]:
    raw_delta = best["delta_vs_raw_post_news"]
    core_delta = best["delta_vs_core"]
    raw_improves = (
        raw_delta["windows_ev_improved"] >= 2
        and raw_delta["windows_ev_regressed"] == 0
    )
    core_non_negative = core_delta["windows_ev_regressed"] == 0
    material_vs_core = bool(
        (core_delta["aggregate_ev_delta_pct"] is not None and core_delta["aggregate_ev_delta_pct"] > 0.10)
        or (core_delta["aggregate_pnl_delta_pct"] is not None and core_delta["aggregate_pnl_delta_pct"] > 0.05)
    )
    material_vs_raw = bool(
        (raw_delta["aggregate_ev_delta_pct"] is not None and raw_delta["aggregate_ev_delta_pct"] > 0.10)
        or (raw_delta["aggregate_pnl_delta_pct"] is not None and raw_delta["aggregate_pnl_delta_pct"] > 0.05)
    )
    selected_count = _selected_trade_count(best)
    drawdown_core_worst = max(
        float(row.get("max_drawdown_pct") or 0.0)
        for row in core_delta["by_window"].values()
    )
    drawdown_raw_worst = max(
        float(row.get("max_drawdown_pct") or 0.0)
        for row in raw_delta["by_window"].values()
    )
    selected_floor = selected_count >= 8
    drawdown_guard = drawdown_core_worst <= 0.02 and drawdown_raw_worst <= 0.01
    passed = bool(
        raw_improves
        and core_non_negative
        and material_vs_core
        and material_vs_raw
        and selected_floor
        and drawdown_guard
    )
    return {
        "passed": passed,
        "raw_post_news_improves_in_2plus_windows_without_ev_regression": raw_improves,
        "core_ev_non_negative_all_windows": core_non_negative,
        "material_vs_core": material_vs_core,
        "material_vs_raw_post_news": material_vs_raw,
        "selected_trade_count": selected_count,
        "selected_trade_count_floor": selected_floor,
        "max_drawdown_worsening_vs_core": _round(drawdown_core_worst, 6),
        "max_drawdown_worsening_vs_raw_post_news": _round(drawdown_raw_worst, 6),
        "drawdown_guard": drawdown_guard,
        "acceptance_rule": (
            "A pre-event RS20 context gate must improve raw post-news EV in at "
            "least two windows with no EV regression, remain non-negative versus "
            "core in all windows, be material versus both core and raw post-news, "
            "retain at least 8 selected event trades, and keep drawdown drift bounded."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Post-News Pre-Event RS20 Context",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Single variable: pre-event 20-trading-day ticker return minus SPY return inside the locked PEAD-like post-news continuation surface.",
        "",
        "| Stack | Window | EV | EV delta vs core | EV delta vs raw | PnL delta vs core | PnL delta vs raw | Event trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    raw = payload["raw_post_news"]
    for label in WINDOWS:
        after = raw["after_metrics"][label]
        core_delta = raw["delta_vs_core"]["by_window"][label]
        trades = raw["shadow_metrics"][label]["selected_trade_count"]
        lines.append(
            f"| raw_post_news | {label} | {after['expected_value_score']:.4f} | "
            f"{core_delta['expected_value_score']:+.4f} | n/a | "
            f"{core_delta['total_pnl']:+.2f} | n/a | {trades} |"
        )
    for name, result in payload["variant_results"].items():
        for label in WINDOWS:
            after = result["after_metrics"][label]
            core_delta = result["delta_vs_core"]["by_window"][label]
            raw_delta = result["delta_vs_raw_post_news"]["by_window"][label]
            trades = result["shadow_metrics"][label]["selected_trade_count"]
            lines.append(
                f"| {name} | {label} | {after['expected_value_score']:.4f} | "
                f"{core_delta['expected_value_score']:+.4f} | "
                f"{raw_delta['expected_value_score']:+.4f} | "
                f"{core_delta['total_pnl']:+.2f} | {raw_delta['total_pnl']:+.2f} | {trades} |"
            )
    lines.extend(
        [
            "",
            "## Best Variant",
            "",
            f"- Best variant: `{payload['best_variant']}`",
            f"- Aggregate EV delta vs raw post-news: `{payload['best_result']['delta_vs_raw_post_news']['aggregate_ev_delta']:+.4f}`",
            f"- Aggregate PnL delta vs raw post-news: `${payload['best_result']['delta_vs_raw_post_news']['aggregate_pnl_delta']:+,.2f}`",
            f"- Aggregate EV delta vs core: `{payload['best_result']['delta_vs_core']['aggregate_ev_delta']:+.4f}`",
            f"- Aggregate PnL delta vs core: `${payload['best_result']['delta_vs_core']['aggregate_pnl_delta']:+,.2f}`",
            f"- Gate 4 passed: `{payload['gate4']['passed']}`",
            "",
            "## Interpretation",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only alpha search. No shared policy, run adapter, backtester adapter, order path, ranking, sizing, LLM prompt, or live universe changed.",
            "",
        ]
    )
    return "\n".join(lines)


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = base._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        core_result = base._load_core_result(window)
        core_results[label] = core_result
        core_metrics[label] = base._core_metrics(core_result)

    raw = _run_event_stack(
        prices=prices,
        core_results=core_results,
        core_metrics=core_metrics,
        variant=None,
    )

    variants: dict[str, dict[str, Any]] = OrderedDict()
    for name, spec in VARIANTS.items():
        result = _run_event_stack(
            prices=prices,
            core_results=core_results,
            core_metrics=core_metrics,
            variant=spec,
        )
        result["parameters"] = spec
        result["delta_vs_raw_post_news"] = _variant_delta(
            raw["after_metrics"],
            result["after_metrics"],
        )
        variants[name] = result

    best_name = _best_variant(variants)
    best = variants[best_name]
    gate4 = _gate4(best)
    decision = (
        "accepted_shadow_lead_needs_shared_adapter"
        if gate4["passed"]
        else "rejected_pre_event_rs20_context_gate"
    )
    status = "shadow_only" if gate4["passed"] else "rejected"
    decision_rationale = (
        "The pre-event RS20 context gate passed the replay gate, but it remains "
        "a shadow lead until a shared default-off adapter and forward replacement "
        "evidence exist."
        if gate4["passed"]
        else (
            "Pre-event RS20 context did not improve the locked post-news "
            "continuation surface enough to justify promotion. This rejects "
            "RS20 sign/5pp gates as the next same-sample post-news discriminator."
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "change_type": "shadow_event_quality_gate",
        "changed_variable": "post_news_pre_event_rs20_context_gate",
        "single_causal_variable": "post_news_pre_event_rs20_context_gate",
        "hypothesis": (
            "Within the PEAD-like post-news continuation pattern, event candidates "
            "with stronger pre-event 20-day relative strength versus SPY should "
            "have better continuation value than pre-event laggards."
        ),
        "alpha_hypothesis": {
            "category": "entry/event-quality",
            "why_this_now": (
                "LLM soft-ranking remains data-limited, while item-composition "
                "and surprise-direction gates were rejected. This tests an "
                "orthogonal PIT OHLCV context variable already compatible with "
                "the accepted RS20 mechanism."
            ),
        },
        "parameters": {
            "locked_from_exp_20260509_020": {
                "event_subtype": base.EVENT_SUBTYPE,
                "event_reaction_min_pct": base.EVENT_REACTION_MIN_PCT,
                "event_volume_ratio_min": base.EVENT_VOLUME_RATIO_MIN,
                "volume_lookback_trading_days": base.EVENT_REACTION_LOOKBACK_DAYS,
                "entry": "next trading day open after event day",
                "exit": f"close on trading day +{base.POST_EVENT_HOLD_TRADING_DAYS} from event day",
                "event_notional_usd": base.EVENT_NOTIONAL,
                "round_trip_cost_pct": base.ROUND_TRIP_COST_PCT,
                "max_active_positions": base.MAX_ACTIVE_POST_NEWS_POSITIONS,
            },
            "rs20_definition": (
                "ticker 20-trading-day close return minus SPY 20-trading-day "
                "close return, ending on the close before event day"
            ),
            "lookback_days": LOOKBACK_DAYS,
            "variants": VARIANTS,
            "locked_variables": [
                "core A/B signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "add-ons",
                "LLM/news prompts",
                "event type/subtype",
                "event reaction threshold",
                "event volume threshold",
                "event hold period",
                "event notional",
                "event capacity",
                "production order path",
            ],
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
        "historical_experiment_check": {
            "exp-20260509-020": (
                "Raw post-news continuation was positive but not enough for "
                "production promotion; semantic/context retries must be orthogonal."
            ),
            "exp-20260511-027": (
                "Item-composition gates were rejected; this does not use 7.01/8.01/5.02 composition."
            ),
            "exp-20260511-029": (
                "Surprise-direction gates were rejected; this does not use the sparse surprise_direction field."
            ),
            "why_not_llm_soft_ranking": (
                "Production-aligned LLM ranking sample remains too thin, so this "
                "run uses deterministic OHLCV context instead."
            ),
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three-window fixed snapshots",
            "baseline_metrics": core_metrics,
        },
        "gate2": gate2,
        "gate3": {
            "new_core_filter_added": False,
            "min_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in core_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values()) >= 0.05,
        },
        "before_metrics": {
            "current_core": core_metrics,
            "raw_post_news_original": raw["after_metrics"],
        },
        "after_metrics": {
            name: result["after_metrics"] for name, result in variants.items()
        },
        "delta_metrics": {
            "raw_post_news_vs_core": raw["delta_vs_core"],
            "rs20_gate_vs_core": {
                name: result["delta_vs_core"] for name, result in variants.items()
            },
            "rs20_gate_vs_raw_post_news": {
                name: result["delta_vs_raw_post_news"] for name, result in variants.items()
            },
        },
        "raw_post_news": raw,
        "variant_results": variants,
        "best_variant": best_name,
        "best_result": best,
        "expected_value_score_delta": best["delta_vs_raw_post_news"][
            "aggregate_ev_delta"
        ],
        "gate4": gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": "This run deliberately avoids the LLM replay coverage bottleneck.",
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if gate4["passed"] else decision_rationale,
        "next_evidence_needed": (
            "Do not retry nearby post-news RS20 sign or 5pp gates on this frozen "
            "sample; future post-news work needs closed forward replacement value "
            "or a richer same-accession earnings-quality field."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG_JSONL),
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Post-news pre-event RS20 context",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta_vs_raw": payload["expected_value_score_delta"],
            "gate4": payload["gate4"],
            "summary": payload["decision_rationale"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "expected_value_score_delta_vs_raw": payload[
                        "expected_value_score_delta"
                    ],
                    "gate4": payload["gate4"],
                    "artifact": str(OUT_JSON),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
