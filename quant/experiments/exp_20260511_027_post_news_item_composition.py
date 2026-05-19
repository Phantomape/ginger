"""exp-20260511-027 post-news 8-K item-composition gate.

Alpha search, replay-only. This tests one causal dimension on the rejected but
positive PEAD-like post-news continuation surface from exp-20260509-020:
whether clean Item 2.02 result releases are better than 8-Ks bundled with
auxiliary disclosure items.
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


EXPERIMENT_ID = "exp-20260511-027"
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
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = base.WINDOWS
AUXILIARY_ITEMS = ("7.01", "8.01", "5.02", "5.07", "3.03")
VARIANTS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "exclude_auxiliary_items",
            {
                "gate": "exclude_auxiliary_items",
                "description": "Skip Item 2.02 events bundled with 7.01/8.01/5.02/5.07/3.03.",
            },
        ),
        (
            "pure_item_2_02_only",
            {
                "gate": "pure_item_2_02_only",
                "description": "Keep only clean Item 2.02 releases with no listed auxiliary item.",
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


def _title(row: dict[str, Any]) -> str:
    return str(row.get("title") or "")


def _has_auxiliary_item(row: dict[str, Any]) -> bool:
    title = _title(row)
    return any(item in title for item in AUXILIARY_ITEMS)


def _pure_item_2_02(row: dict[str, Any]) -> bool:
    return "2.02" in _title(row) and not _has_auxiliary_item(row)


def _gate_fn(gate: str) -> Callable[[dict[str, Any]], bool]:
    if gate == "exclude_auxiliary_items":
        return lambda row: not _has_auxiliary_item(row)
    if gate == "pure_item_2_02_only":
        return _pure_item_2_02
    raise ValueError(f"Unknown item-composition gate: {gate}")


def _apply_gate(
    candidates: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    gate: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predicate = _gate_fn(gate)
    kept: list[dict[str, Any]] = []
    gated_out: list[dict[str, Any]] = []
    for row in candidates:
        if predicate(row):
            kept.append(row)
        else:
            gated_out.append({**row, "status": f"item_composition_rejected:{gate}"})
    return kept, rejected + gated_out


def _item_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = OrderedDict()
    checks: "OrderedDict[str, Callable[[dict[str, Any]], bool]]" = OrderedDict(
        [
            ("has_auxiliary_item", _has_auxiliary_item),
            ("pure_item_2_02_only", _pure_item_2_02),
            ("has_7_01", lambda row: "7.01" in _title(row)),
            ("has_8_01", lambda row: "8.01" in _title(row)),
            ("has_5_02", lambda row: "5.02" in _title(row)),
        ]
    )
    for name, predicate in checks.items():
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


def _run_event_stack(
    *,
    prices: dict[str, list[dict[str, Any]]],
    core_results: dict[str, dict[str, Any]],
    core_metrics: dict[str, dict[str, Any]],
    gate: str | None,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    shadow_metrics: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        candidates, rejected = base._build_candidates(
            prices,
            start=window["start"],
            end=window["end"],
        )
        if gate:
            candidates, rejected = _apply_gate(candidates, rejected, gate)
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
            "gate": gate or "none",
            "qualified_before_item_gate": len(candidates)
            + sum(1 for row in rejected if str(row.get("status", "")).startswith("item_composition_rejected")),
            "qualified_after_item_gate": len(candidates),
            "selected_trade_count": len(selected),
            "capacity_skipped_count": len(capacity_skipped),
            "selected_pnl": round(sum(float(row.get("pnl") or 0.0) for row in selected), 2),
            "selected_win_rate": quality["selected_win_rate"],
            "selected_avg_event_reaction_pct": quality["selected_avg_event_reaction_pct"],
            "selected_avg_volume_ratio": quality["selected_avg_volume_ratio"],
            "selected_by_ticker": quality["selected_by_ticker"],
            "item_composition": _item_summary(selected),
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


def _gate4(
    best: dict[str, Any],
) -> dict[str, Any]:
    raw_delta = best["delta_vs_raw_post_news"]
    core_delta = best["delta_vs_core"]
    raw_improves = raw_delta["windows_ev_improved"] >= 2 and raw_delta["windows_ev_regressed"] == 0
    core_non_negative = core_delta["windows_ev_regressed"] == 0
    material_vs_core = bool(
        (core_delta["aggregate_ev_delta_pct"] is not None and core_delta["aggregate_ev_delta_pct"] > 0.10)
        or (core_delta["aggregate_pnl_delta_pct"] is not None and core_delta["aggregate_pnl_delta_pct"] > 0.05)
    )
    material_vs_raw = bool(
        (raw_delta["aggregate_ev_delta_pct"] is not None and raw_delta["aggregate_ev_delta_pct"] > 0.10)
        or (raw_delta["aggregate_pnl_delta_pct"] is not None and raw_delta["aggregate_pnl_delta_pct"] > 0.05)
    )
    passed = bool(raw_improves and core_non_negative and material_vs_core and material_vs_raw)
    return {
        "passed": passed,
        "raw_post_news_improves_in_2plus_windows_without_ev_regression": raw_improves,
        "core_ev_non_negative_all_windows": core_non_negative,
        "material_vs_core": material_vs_core,
        "material_vs_raw_post_news": material_vs_raw,
        "acceptance_rule": (
            "An item-composition gate must improve raw post-news EV in at least "
            "two windows with no EV regression, remain non-negative versus core "
            "in all windows, and be material versus both core and raw post-news."
        ),
    }


def _gate2_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"passed": False, "path": _repo_rel(path), "missing": "file"}
    payload = json.loads(path.read_text(encoding="utf-8"))
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


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Post-News Item Composition",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Single variable: 8-K item-composition gate inside the locked exp-20260509-020 post-news continuation pattern.",
        "",
        "| Stack | Window | EV | EV Δ vs core | EV Δ vs raw | PnL Δ vs core | PnL Δ vs raw | Event trades |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
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
        gate=None,
    )

    variants: dict[str, dict[str, Any]] = OrderedDict()
    for name, spec in VARIANTS.items():
        result = _run_event_stack(
            prices=prices,
            core_results=core_results,
            core_metrics=core_metrics,
            gate=spec["gate"],
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
        else "rejected_item_composition_gate"
    )
    status = "shadow_only" if gate4["passed"] else "rejected"
    decision_rationale = (
        "The item-composition gate passed the pre-registered replay gate, but it "
        "is only a shadow lead until a shared default-off adapter and forward "
        "replacement-value evidence exist."
        if gate4["passed"]
        else (
            "The clean Item 2.02 / auxiliary-item discriminator did not improve "
            "the raw post-news continuation surface enough to justify promotion. "
            "This rejects nearby item-composition gating on the frozen sample."
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "change_type": "shadow_event_quality_gate",
        "changed_variable": "post_news_8k_item_composition_gate",
        "single_causal_variable": "post_news_8k_item_composition_gate",
        "hypothesis": (
            "Within the PEAD-like post-news continuation pattern, clean Item 2.02 "
            "earnings/result releases should outperform 8-Ks bundled with "
            "auxiliary disclosure items."
        ),
        "alpha_hypothesis": {
            "category": "entry/event-quality",
            "why_this_now": (
                "LLM soft-ranking remains data-limited; recent Space, SEC, slot, "
                "RS20, and sector-risk loops have anti-repeat guardrails. This "
                "tests an orthogonal candidate-pool quality feature already "
                "present in PIT event snapshots."
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
            "variants": VARIANTS,
            "auxiliary_items": list(AUXILIARY_ITEMS),
            "locked_variables": [
                "core A/B signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "add-ons",
                "LLM/news prompts",
                "price and volume thresholds",
                "event hold period",
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
                "Raw post-news continuation was positive but immaterial; only "
                "orthogonal semantic earnings-quality retries were allowed."
            ),
            "exp-20260510-025_and_027": (
                "SEC financial-report T+1 queue is frozen for forward observation; "
                "this experiment does not retune that queue."
            ),
            "recent_space_and_slot_guardrails": (
                "Avoids Space, global slot, RS20 scalar, sector cluster, and LLM "
                "soft-ranking retunes."
            ),
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three-window fixed snapshots",
            "baseline_metrics": core_metrics,
        },
        "gate2": _gate2_open_positions(),
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
            "item_gate_vs_core": {
                name: result["delta_vs_core"] for name, result in variants.items()
            },
            "item_gate_vs_raw_post_news": {
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
            "Do not retry nearby item-composition gates on this frozen sample; "
            "future work needs closed forward post-news replacement value or a "
            "richer semantic earnings-quality feature."
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
            "title": "Post-news item-composition gate",
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
