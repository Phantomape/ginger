"""exp-20260511-029 post-news surprise-direction semantic gate.

Alpha search, replay-only. This tests one semantic event-quality variable on
the locked PEAD-like post-news continuation surface from exp-20260509-020:
whether the PIT `surprise_direction` label improves candidate quality after
the existing price/volume confirmation has already fired.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260509_020_post_news_continuation_entry_pattern as base  # noqa: E402
from experiments import exp_20260511_027_post_news_item_composition as item_base  # noqa: E402


EXPERIMENT_ID = "exp-20260511-029"
STEM = "post_news_surprise_direction"
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
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

WINDOWS = base.WINDOWS
VARIANTS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "unknown_only",
            {
                "gate": "unknown_only",
                "description": "Keep only rows where surprise_direction is unknown.",
            },
        ),
        (
            "positive_only",
            {
                "gate": "positive_only",
                "description": "Keep only rows where surprise_direction is positive.",
            },
        ),
        (
            "exclude_directional",
            {
                "gate": "exclude_directional",
                "description": "Drop positive, negative, and mixed surprise_direction rows.",
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


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("surprise_direction") or "unknown").lower()


def _gate_fn(gate: str) -> Callable[[dict[str, Any]], bool]:
    if gate == "unknown_only":
        return lambda row: _direction(row) == "unknown"
    if gate == "positive_only":
        return lambda row: _direction(row) == "positive"
    if gate == "exclude_directional":
        return lambda row: _direction(row) not in {"positive", "negative", "mixed"}
    raise ValueError(f"Unknown surprise-direction gate: {gate}")


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
            gated_out.append(
                {**row, "status": f"surprise_direction_rejected:{gate}"}
            )
    return kept, rejected + gated_out


def _direction_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = OrderedDict()
    for direction, group in sorted(
        ((key, list(items)) for key, items in _group_by_direction(rows).items()),
        key=lambda item: item[0],
    ):
        wins = sum(1 for row in group if float(row.get("pnl") or 0.0) > 0.0)
        pnl = sum(float(row.get("pnl") or 0.0) for row in group)
        summary[direction] = {
            "trade_count": len(group),
            "wins": wins,
            "win_rate": round(wins / len(group), 4) if group else None,
            "pnl": round(pnl, 2),
        }
    return summary


def _group_by_direction(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        grouped.setdefault(_direction(row), []).append(row)
    return grouped


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
        qualified_before_gate = len(candidates)
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
        rejection_counts = quality["rejection_status_counts"]
        shadow_metrics[label] = {
            "gate": gate or "none",
            "qualified_before_surprise_gate": qualified_before_gate,
            "qualified_after_surprise_gate": len(candidates),
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
            "selected_by_surprise_direction": _direction_summary(selected),
            "rejection_status_counts": rejection_counts,
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


def _gate4(best: dict[str, Any]) -> dict[str, Any]:
    raw_delta = best["delta_vs_raw_post_news"]
    core_delta = best["delta_vs_core"]
    raw_improves = (
        raw_delta["windows_ev_improved"] >= 2
        and raw_delta["windows_ev_regressed"] == 0
    )
    core_non_negative = core_delta["windows_ev_regressed"] == 0
    material_vs_core = bool(
        (
            core_delta["aggregate_ev_delta_pct"] is not None
            and core_delta["aggregate_ev_delta_pct"] > 0.10
        )
        or (
            core_delta["aggregate_pnl_delta_pct"] is not None
            and core_delta["aggregate_pnl_delta_pct"] > 0.05
        )
    )
    material_vs_raw = bool(
        (
            raw_delta["aggregate_ev_delta_pct"] is not None
            and raw_delta["aggregate_ev_delta_pct"] > 0.10
        )
        or (
            raw_delta["aggregate_pnl_delta_pct"] is not None
            and raw_delta["aggregate_pnl_delta_pct"] > 0.05
        )
    )
    selected_trades = sum(
        int(row["selected_trade_count"]) for row in best["shadow_metrics"].values()
    )
    passed = bool(
        raw_improves
        and core_non_negative
        and material_vs_core
        and material_vs_raw
        and selected_trades >= 8
    )
    return {
        "passed": passed,
        "raw_post_news_improves_in_2plus_windows_without_ev_regression": raw_improves,
        "core_ev_non_negative_all_windows": core_non_negative,
        "material_vs_core": material_vs_core,
        "material_vs_raw_post_news": material_vs_raw,
        "selected_trade_count_floor": selected_trades >= 8,
        "selected_trade_count": selected_trades,
        "acceptance_rule": (
            "A surprise-direction gate must improve raw post-news EV in at least "
            "two windows with no EV regression, remain non-negative versus core "
            "in all windows, be material versus both core and raw post-news, "
            "and retain at least 8 selected event trades."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Post-News Surprise-Direction Gate",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Single variable: `surprise_direction` semantic gate inside the locked exp-20260509-020 post-news continuation pattern.",
        "",
        "| Stack | Window | EV | EV delta vs core | EV delta vs raw | PnL delta vs core | PnL delta vs raw | Event trades |",
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
    best = payload["best_result"]
    lines.extend(
        [
            "",
            "## Best Variant",
            "",
            f"- Best variant: `{payload['best_variant']}`",
            f"- Aggregate EV delta vs raw post-news: `{best['delta_vs_raw_post_news']['aggregate_ev_delta']:+.4f}`",
            f"- Aggregate PnL delta vs raw post-news: `${best['delta_vs_raw_post_news']['aggregate_pnl_delta']:+,.2f}`",
            f"- Aggregate EV delta vs core: `{best['delta_vs_core']['aggregate_ev_delta']:+.4f}`",
            f"- Aggregate PnL delta vs core: `${best['delta_vs_core']['aggregate_pnl_delta']:+,.2f}`",
            f"- Gate 4 passed: `{payload['gate4']['passed']}`",
            "",
            "## Direction Attribution",
            "",
        ]
    )
    for label, metrics in raw["shadow_metrics"].items():
        lines.append(
            f"- raw_post_news {label}: {metrics['selected_by_surprise_direction']}"
        )
    lines.extend(
        [
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


def _append_once(path: Path, marker: str, text: str) -> None:
    current = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    if marker in current:
        return
    path.write_text(current.rstrip() + "\n" + text.lstrip(), encoding="utf-8")


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
        else "rejected_surprise_direction_gate"
    )
    status = "shadow_only" if gate4["passed"] else "rejected"
    decision_rationale = (
        "The surprise-direction gate passed the pre-registered replay gate, but "
        "it is only a shadow lead until a shared default-off adapter and forward "
        "replacement-value evidence exist."
        if gate4["passed"]
        else (
            "The PIT surprise_direction semantic label did not improve the locked "
            "post-news continuation surface enough to justify promotion. Explicit "
            "positive/negative labels were sparse and did not rescue the raw "
            "PEAD-like sleeve from the materiality problem."
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "change_type": "shadow_event_quality_gate",
        "changed_variable": "post_news_surprise_direction_gate",
        "single_causal_variable": "post_news_surprise_direction_gate",
        "hypothesis": (
            "Within the PEAD-like post-news continuation pattern, PIT "
            "surprise_direction should separate higher-quality earnings-result "
            "events from generic price/volume-confirmed 8-K rows."
        ),
        "alpha_hypothesis": {
            "category": "entry/event_quality",
            "why_this_now": (
                "LLM soft-ranking remains data-limited; Space and SEC T+1 slices "
                "have fresh anti-repeat guardrails. The playbook permits post-news "
                "retries only with an orthogonal semantic earnings-quality field."
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
            "locked_variables": [
                "core A/B signal generation",
                "core candidate ranking",
                "core sizing",
                "core exits",
                "add-ons",
                "LLM/news prompts",
                "price and volume thresholds",
                "event hold period",
                "event notional",
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
            "exp-20260511-027": (
                "8-K item-composition gating was rejected; this does not reuse "
                "item-code composition and instead tests event_shocks semantic "
                "direction."
            ),
            "recent_guardrails": (
                "Avoids Space risk scalar repeats, SEC financial-report queue "
                "retunes, broad slot sweeps, and LLM soft-ranking."
            ),
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three-window fixed snapshots",
            "baseline_metrics": core_metrics,
        },
        "gate2": item_base._gate2_open_positions(),
        "gate3": {
            "new_core_filter_added": False,
            "min_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0)
                for row in core_metrics.values()
            ),
            "passed": min(
                float(row.get("survival_rate") or 0.0)
                for row in core_metrics.values()
            )
            >= 0.05,
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
            "surprise_gate_vs_core": {
                name: result["delta_vs_core"] for name, result in variants.items()
            },
            "surprise_gate_vs_raw_post_news": {
                name: result["delta_vs_raw_post_news"]
                for name, result in variants.items()
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
            "why_no_llm_change": (
                "This experiment uses the deterministic event_shocks semantic "
                "field and deliberately avoids the LLM replay coverage bottleneck."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if gate4["passed"] else decision_rationale,
        "next_evidence_needed": (
            "Do not retry nearby surprise_direction buckets on this frozen sample; "
            "future post-news work needs closed forward replacement value or a "
            "richer same-accession earnings-quality field with better coverage."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG_JSONL),
            _repo_rel(CURRENT_STATE_MD),
            _repo_rel(PLAYBOOK_MD),
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Post-news surprise-direction gate",
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

    state_text = f"""

## {EXPERIMENT_ID} Post-news surprise-direction gate

- timestamp: {payload['timestamp']}
- lane: alpha_search
- decision: {payload['decision']}
- changed_variable: {payload['changed_variable']}
- best_variant: {payload['best_variant']}
- expected_value_score_delta_vs_raw: {payload['expected_value_score_delta']}
- gate4_passed: {payload['gate4']['passed']}
- interpretation: {payload['decision_rationale']}
- production_impact: {payload['production_impact']}
- artifact: `{OUT_JSON.relative_to(REPO_ROOT)}`
"""
    _append_once(CURRENT_STATE_MD, EXPERIMENT_ID, state_text)

    playbook_text = f"""

### {EXPERIMENT_ID} Post-news surprise-direction gate

- Decision: {payload['decision']}.
- Tested variable: `{payload['changed_variable']}` inside the locked PEAD-like post-news continuation surface.
- Best variant: `{payload['best_variant']}`.
- Aggregate EV delta vs raw post-news: `{payload['expected_value_score_delta']}`.
- Interpretation: {payload['decision_rationale']}
- Do not repeat nearby `surprise_direction` bucket gates on the frozen sample without forward outcomes or a richer same-accession earnings-quality field.
"""
    _append_once(PLAYBOOK_MD, EXPERIMENT_ID, playbook_text)


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
