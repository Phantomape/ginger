"""exp-20260511-025 post-news 8-K item-composition gate.

Alpha search, replay-only. This tests an orthogonal semantic discriminator for
the previously rejected-but-positive PEAD-like post-news continuation sleeve:
whether earnings/result 8-Ks with auxiliary filing items behave differently from
clean Item 2.02 result releases.

Locked from exp-20260509-020:
    * event subtype: high-confidence 8k_item_2_02
    * event-day reaction: > +1%
    * event-day volume: >= 1.5x prior 20 trading days
    * entry: next open
    * exit: event day +10 trading-day close
    * fixed event notional and max active positions

Only the filing item-composition gate changes.
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

from experiments import exp_20260509_020_post_news_continuation_entry_pattern as base  # noqa: E402


EXPERIMENT_ID = "exp-20260511-025"
STEM = "post_news_item_composition"
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

WINDOWS = base.WINDOWS
AUXILIARY_ITEMS = ("7.01", "8.01", "5.02", "5.07", "3.03")

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "raw_post_news_original",
            {
                "description": "Original exp-20260509-020 PEAD-like post-news rule; no item-composition gate.",
                "gate": "none",
            },
        ),
        (
            "exclude_reg_fd_7_01",
            {
                "description": "Skip candidates whose 8-K title includes Item 7.01 Reg FD disclosure.",
                "gate": "exclude_reg_fd_7_01",
            },
        ),
        (
            "pure_item_2_02_only",
            {
                "description": "Keep only clean Item 2.02 result releases with no auxiliary 7.01/8.01/5.02/5.07/3.03 items.",
                "gate": "pure_item_2_02_only",
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
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _title(row: dict[str, Any]) -> str:
    return str(row.get("title") or "")


def _has_item(row: dict[str, Any], item: str) -> bool:
    return item in _title(row)


def _pure_item_2_02(row: dict[str, Any]) -> bool:
    title = _title(row)
    return "2.02" in title and all(item not in title for item in AUXILIARY_ITEMS)


def _gate_fn(gate: str) -> Callable[[dict[str, Any]], bool]:
    if gate == "none":
        return lambda row: True
    if gate == "exclude_reg_fd_7_01":
        return lambda row: not _has_item(row, "7.01")
    if gate == "pure_item_2_02_only":
        return _pure_item_2_02
    raise ValueError(f"Unknown gate: {gate}")


def _variant_candidates(
    candidates: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    gate: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predicate = _gate_fn(gate)
    kept: list[dict[str, Any]] = []
    item_rejected: list[dict[str, Any]] = []
    for row in candidates:
        if predicate(row):
            kept.append(row)
        else:
            item_rejected.append(
                {
                    **row,
                    "status": f"item_composition_rejected:{gate}",
                }
            )
    return kept, rejected + item_rejected


def _item_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = OrderedDict()
    for name, predicate in OrderedDict(
        [
            ("has_7_01", lambda row: _has_item(row, "7.01")),
            ("has_8_01", lambda row: _has_item(row, "8.01")),
            ("has_5_02", lambda row: _has_item(row, "5.02")),
            ("pure_item_2_02_only", _pure_item_2_02),
        ]
    ).items():
        selected = [row for row in rows if predicate(row)]
        wins = sum(1 for row in selected if float(row.get("pnl") or 0.0) > 0.0)
        pnl = sum(float(row.get("pnl") or 0.0) for row in selected)
        summary[name] = {
            "trade_count": len(selected),
            "wins": wins,
            "win_rate": round(wins / len(selected), 4) if selected else None,
            "pnl": round(pnl, 2),
        }
    return summary


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return base._aggregate_delta(before, after)


def _variant_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return _aggregate_delta(before, after)


def _run_variant(
    variant_name: str,
    variant: dict[str, Any],
    *,
    prices: dict[str, list[dict[str, Any]]],
    core_results: dict[str, dict[str, Any]],
    core_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    shadow_metrics: dict[str, dict[str, Any]] = OrderedDict()
    selected_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    skipped_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()

    for label, window in WINDOWS.items():
        candidates, rejected = base._build_candidates(
            prices,
            start=window["start"],
            end=window["end"],
        )
        gated_candidates, gated_rejected = _variant_candidates(
            candidates,
            rejected,
            str(variant["gate"]),
        )
        selected, capacity_skipped = base._select_trades(gated_candidates)
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
        selected_by_window[label] = selected
        skipped_by_window[label] = gated_rejected + capacity_skipped
        quality = base._candidate_quality(selected, gated_rejected + capacity_skipped)
        shadow_metrics[label] = {
            "event_subtype": base.EVENT_SUBTYPE,
            "gate": variant["gate"],
            "raw_candidate_count": len(candidates) + len(rejected),
            "qualified_before_item_gate": len(candidates),
            "qualified_after_item_gate": len(gated_candidates),
            "selected_trade_count": len(selected),
            "capacity_skipped_count": len(capacity_skipped),
            "selected_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in selected),
                2,
            ),
            "selected_win_rate": quality["selected_win_rate"],
            "selected_avg_event_reaction_pct": quality[
                "selected_avg_event_reaction_pct"
            ],
            "selected_avg_volume_ratio": quality["selected_avg_volume_ratio"],
            "selected_by_ticker": quality["selected_by_ticker"],
            "item_composition": _item_summary(selected),
            "rejection_status_counts": quality["rejection_status_counts"],
            "selected_trades": selected,
        }

    return {
        "variant": variant_name,
        "parameters": variant,
        "after_metrics": after_metrics,
        "delta_vs_core": _variant_delta(core_metrics, after_metrics),
        "shadow_metrics": shadow_metrics,
        "selected_by_window": selected_by_window,
        "skipped_by_window": skipped_by_window,
    }


def _gate_summary(delta: dict[str, Any], *, reference_name: str) -> dict[str, Any]:
    by_window = delta["by_window"]
    late_ev = by_window["late_strong"]["expected_value_score"]
    aggregate_ev_delta = delta["aggregate_ev_delta"]
    aggregate_pnl_delta = delta["aggregate_pnl_delta"]
    aggregate_ev_delta_pct = delta["aggregate_ev_delta_pct"]
    aggregate_pnl_delta_pct = delta["aggregate_pnl_delta_pct"]
    no_ev_regression = delta["windows_ev_regressed"] == 0
    material = bool(
        (aggregate_ev_delta_pct is not None and aggregate_ev_delta_pct > 0.10)
        or (aggregate_pnl_delta_pct is not None and aggregate_pnl_delta_pct > 0.05)
    )
    passed = bool(
        no_ev_regression
        and late_ev >= 0
        and aggregate_ev_delta > 0
        and aggregate_pnl_delta > 0
        and material
    )
    return {
        "reference": reference_name,
        "passed": passed,
        "no_ev_regression": no_ev_regression,
        "late_strong_ev_non_negative": late_ev >= 0,
        "aggregate_ev_positive": aggregate_ev_delta > 0,
        "aggregate_pnl_positive": aggregate_pnl_delta > 0,
        "aggregate_material": material,
        "acceptance_rule": (
            "Require no EV-regressing canonical window, late_strong non-negative, "
            "aggregate EV/PnL positive, and aggregate EV >10% or PnL >5% before "
            "any adapter/promotion work."
        ),
    }


def _choose_best(results: dict[str, dict[str, Any]]) -> str:
    return max(
        results,
        key=lambda name: (
            results[name]["delta_vs_core"]["aggregate_ev_delta"],
            results[name]["delta_vs_core"]["aggregate_pnl_delta"],
            results[name]["after_metrics"]["late_strong"]["expected_value_score"],
        ),
    )


def _delta_table_row(
    variant_name: str,
    result: dict[str, Any],
    label: str,
) -> str:
    after = result["after_metrics"][label]
    delta = result["delta_vs_core"]["by_window"][label]
    shadow = result["shadow_metrics"][label]
    return (
        f"| {variant_name} | {label} | {after['expected_value_score']:.4f} | "
        f"{delta['expected_value_score']:+.4f} | ${after['total_pnl']:,.2f} | "
        f"${delta['total_pnl']:+,.2f} | {after['sharpe_daily']:.2f} | "
        f"{after['max_drawdown_pct']:.2%} | {shadow['selected_trade_count']} | "
        f"${shadow['selected_pnl']:+,.2f} |"
    )


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Post-News Item Composition",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search. Tests one causal variable inside the PEAD-like post-news continuation sleeve: the semantic composition of the 8-K filing items.",
        "",
        "## Three-Window Result",
        "",
        "| Variant | Window | Variant EV | EV Delta Vs Core | Variant PnL | PnL Delta Vs Core | SharpeD | Max DD | Event Trades | Event PnL |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant_name, result in payload["variant_results"].items():
        for label in WINDOWS:
            lines.append(_delta_table_row(variant_name, result, label))

    lines.extend(
        [
            "",
            "## Best Variant",
            "",
            f"- Best variant: `{payload['best_variant']}`",
            f"- Aggregate EV delta vs core: `{payload['best_gate']['delta']['aggregate_ev_delta']:+.4f}`",
            f"- Aggregate PnL delta vs core: `${payload['best_gate']['delta']['aggregate_pnl_delta']:+,.2f}`",
            f"- EV windows improved/regressed: `{payload['best_gate']['delta']['windows_ev_improved']}` / `{payload['best_gate']['delta']['windows_ev_regressed']}`",
            f"- Gate passed: `{payload['gate4']['passed']}`",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay only. No production orders, shared core policy, sizing, ranking, exits, LLM/news prompt, or live universe changed. A positive future version would need a shared default-off post-news sleeve adapter and parity tests before any live/default promotion.",
            "",
        ]
    )
    return "\n".join(lines)


def _append_experiment_log(payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
        lines.append(compact)
        EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    EXPERIMENT_LOG.write_text(compact + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = base._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        result = base._load_core_result(window)
        core_results[label] = result
        core_metrics[label] = base._core_metrics(result)

    variant_results: dict[str, dict[str, Any]] = OrderedDict()
    for variant_name, variant in VARIANTS.items():
        variant_results[variant_name] = _run_variant(
            variant_name,
            variant,
            prices=prices,
            core_results=core_results,
            core_metrics=core_metrics,
        )

    raw_delta = variant_results["raw_post_news_original"]["delta_vs_core"]
    for variant_name, result in variant_results.items():
        result["delta_vs_raw_post_news_original"] = (
            None
            if variant_name == "raw_post_news_original"
            else _variant_delta(
                variant_results["raw_post_news_original"]["after_metrics"],
                result["after_metrics"],
            )
        )

    best_variant = _choose_best(variant_results)
    best_result = variant_results[best_variant]
    gate = _gate_summary(best_result["delta_vs_core"], reference_name="current_core")

    decision = "accepted_shadow_lead_needs_shared_adapter" if gate["passed"] else "rejected_semantic_filter_underpowered"
    status = "shadow_only" if gate["passed"] else "rejected"
    if gate["passed"]:
        decision_rationale = (
            "Accepted only as a shadow lead: the item-composition gate clears the "
            "pre-registered three-window materiality and no-regression checks, but "
            "no production/default order path changes until a shared adapter and "
            "forward replacement-value evidence exist."
        )
    else:
        decision_rationale = (
            "Rejected for promotion. The item-composition gate did not clear the "
            "pre-registered Gate 4 rule against the current core: it required no "
            "EV-regressing canonical window, non-negative late_strong EV, positive "
            "aggregate EV/PnL, and aggregate EV >10% or PnL >5%."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "change_type": "shadow_post_news_item_composition_gate",
        "mechanism_family": "post_news_continuation_candidate_pool_extension",
        "hypothesis": (
            "Within the PEAD-like post-news continuation pattern, clean Item 2.02 "
            "earnings/result releases may carry higher continuation quality than "
            "8-Ks bundled with auxiliary disclosure items such as 7.01 or 8.01."
        ),
        "alpha_hypothesis": {
            "category": "entry/event-quality",
            "entry_exit_ranking_or_allocation": "entry",
            "why_this_now": (
                "LLM soft-ranking is sample-limited, core RS20/Space/sector "
                "micro-retunes have recent guardrails, and exp-20260509-020 "
                "explicitly allowed a post-news retry only with an orthogonal "
                "semantic earnings-quality field."
            ),
        },
        "single_causal_variable": "post-news 8-K item-composition gate",
        "parameters": {
            "variants": VARIANTS,
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
            "locked_variables": [
                "core A/B signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "add-ons",
                "LLM/news prompts",
                "event bundle source queues",
                "state-surface rules",
                "price/volume thresholds",
                "event holding period",
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
                "Original price/volume-confirmed post-news continuation was "
                "positive but rejected; playbook allows only an orthogonal "
                "semantic earnings-quality retry."
            ),
            "exp-20260510-003": (
                "Event rotation-surface tilt already has a shared default-off "
                "adapter; do not retune nearby event bundle scalars on this run."
            ),
            "exp-20260510-025_and_027": (
                "SEC financial-report T+1 branch already has a frozen "
                "non-platform observe-only queue; do not retune adjacent slices."
            ),
        },
        "before_metrics": core_metrics,
        "after_metrics": {
            name: result["after_metrics"]
            for name, result in variant_results.items()
        },
        "delta_metrics": {
            "variant_vs_core": {
                name: result["delta_vs_core"]
                for name, result in variant_results.items()
            },
            "raw_post_news_original_vs_core": raw_delta,
            "variant_vs_raw_post_news_original": {
                name: result["delta_vs_raw_post_news_original"]
                for name, result in variant_results.items()
                if name != "raw_post_news_original"
            },
        },
        "variant_results": variant_results,
        "best_variant": best_variant,
        "best_gate": {
            "delta": best_result["delta_vs_core"],
            **gate,
        },
        "expected_value_score_delta": best_result["delta_vs_core"][
            "aggregate_ev_delta"
        ],
        "gate4": {
            "passed": gate["passed"],
            "basis": "Three canonical backtesting.md windows versus current accepted core.",
            "gate": gate,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "production_signal_path_changed": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "This experiment deliberately avoids the current LLM replay "
                "coverage bottleneck."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if gate["passed"] else decision_rationale,
        "risk_of_change": (
            "Filing item composition is visible in historical snapshots, but the "
            "sample remains an event-satellite replay; promotion would require "
            "forward replacement value and a shared default-off adapter."
        ),
        "next_action": (
            "Do not retry nearby post-news price/volume/hold thresholds on this "
            "same sample. If revisited, use fresh forward paper outcomes or a "
            "richer semantic earnings-quality field."
            if not gate["passed"]
            else "Build a shared default-off post-news sleeve adapter and collect forward replacement-value evidence before live/default promotion."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Post-news item-composition gate",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "gate4": payload["gate4"],
            "next_action": payload["next_action"],
        },
    )
    _append_experiment_log(payload)


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
                    "expected_value_score_delta": payload[
                        "expected_value_score_delta"
                    ],
                    "gate4": payload["gate4"],
                    "out_json": str(OUT_JSON),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
