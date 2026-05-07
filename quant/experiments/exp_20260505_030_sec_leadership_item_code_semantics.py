"""exp-20260505-030 SEC leadership item-code semantic discriminator.

Alpha search, not a production strategy change. The already-tested SEC
leadership-change negative-reaction sleeve was standalone-positive but rejected
for promotion because the fixed-notional sleeve was weak in old_thin. This run
keeps the reaction branch frozen and tests one narrower causal variable: whether
item-code context inside 8-K Item 5.02 separates cleaner leadership uncertainty
from mixed governance/procedural filings.
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

from experiments.exp_20260503_051_sec_filing_reaction_drift import WINDOWS, _compact_event  # noqa: E402
from experiments.exp_20260504_026_sec_leadership_event_sleeve import (  # noqa: E402
    _collect_primary_candidates,
    simulate_sleeve,
)


EXPERIMENT_ID = "exp-20260505-030"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "sec_leadership_item_code_semantics.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_leadership_item_code_semantics.md"
)


VARIANTS = OrderedDict(
    [
        (
            "all_leadership_negative_reaction",
            {
                "description": "control: all 5.02 leadership-change negative-reaction candidates",
                "filter": "all",
            },
        ),
        (
            "pure_5_02_only",
            {
                "description": "only Item 5.02 rows with no extra item codes beyond 9.01 exhibits",
                "filter": "pure_5_02",
            },
        ),
        (
            "exclude_governance_mix",
            {
                "description": "exclude 5.02 rows mixed with 5.07/5.03/3.02/3.03 governance items",
                "filter": "exclude_governance_mix",
            },
        ),
        (
            "fd_other_context_only",
            {
                "description": "only 5.02 rows also carrying 7.01/8.01 FD or other-event context",
                "filter": "fd_other_context",
            },
        ),
    ]
)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _item_semantic(candidate: dict[str, Any]) -> str:
    items = {str(item) for item in candidate.get("eight_k_item_codes") or []}
    extra = items - {"5.02", "9.01"}
    if not extra:
        return "pure_5_02"
    if extra & {"7.01", "8.01"}:
        return "fd_or_other_context"
    if extra & {"5.07", "5.03", "3.02", "3.03"}:
        return "governance_mix"
    if extra & {"2.02", "2.05", "4.02"}:
        return "results_or_accounting_mix"
    return "other_mix"


def _candidate_allowed(candidate: dict[str, Any], variant_filter: str) -> bool:
    semantic = _item_semantic(candidate)
    if variant_filter == "all":
        return True
    if variant_filter == "pure_5_02":
        return semantic == "pure_5_02"
    if variant_filter == "exclude_governance_mix":
        return semantic != "governance_mix"
    if variant_filter == "fd_other_context":
        return semantic == "fd_or_other_context"
    raise ValueError(f"unknown variant filter: {variant_filter}")


def _window_pnl(sleeve: dict[str, Any], window: str) -> float:
    summary = (sleeve.get("trade_summary") or {}).get("by_window") or {}
    value = (summary.get(window) or {}).get("total_pnl")
    return float(value or 0.0)


def _variant_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "trade_count",
        "total_pnl",
        "total_return_pct",
        "sharpe_daily",
        "expected_value_score",
        "max_drawdown_pct",
        "win_rate",
        "skipped_count",
    )
    delta: dict[str, Any] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            delta[key] = _round(after_value - before_value, 6)
    delta["by_window_pnl"] = {
        label: _round(_window_pnl(after, label) - _window_pnl(before, label), 2)
        for label in WINDOWS
    }
    return delta


def _candidate_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    by_semantic = Counter(_item_semantic(candidate) for candidate in candidates)
    by_window = Counter(str(candidate.get("window") or "unknown") for candidate in candidates)
    return {
        "candidate_count": len(candidates),
        "by_semantic": dict(by_semantic),
        "by_window": dict(by_window),
        "examples": [_compact_event(candidate) for candidate in candidates[:10]],
    }


def _run_variants(candidates: list[dict[str, Any]], price_map: dict[str, list[dict[str, Any]]]) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, spec in VARIANTS.items():
        selected = [
            candidate
            for candidate in candidates
            if _candidate_allowed(candidate, str(spec["filter"]))
        ]
        sleeve = simulate_sleeve(selected, price_map)
        rows[name] = {
            "description": spec["description"],
            "filter": spec["filter"],
            "candidate_summary": _candidate_summary(selected),
            "sleeve_metrics": sleeve,
        }
    control = rows["all_leadership_negative_reaction"]["sleeve_metrics"]
    for row in rows.values():
        row["delta_vs_all_leadership"] = _variant_delta(row["sleeve_metrics"], control)
    return rows


def _best_variant(variants: OrderedDict[str, dict[str, Any]]) -> str:
    control_name = "all_leadership_negative_reaction"
    ranked = []
    for name, row in variants.items():
        if name == control_name:
            continue
        sleeve = row["sleeve_metrics"]
        ranked.append(
            (
                _round(sleeve.get("expected_value_score"), 8) or -999.0,
                _round(sleeve.get("total_pnl"), 2) or -999999.0,
                -1.0 * (_round(sleeve.get("max_drawdown_pct"), 8) or 1.0),
                name,
            )
        )
    ranked.sort(reverse=True)
    return ranked[0][3]


def _accepted(best: dict[str, Any], control: dict[str, Any]) -> bool:
    sleeve = best["sleeve_metrics"]
    delta = best["delta_vs_all_leadership"]
    by_window = (sleeve.get("trade_summary") or {}).get("by_window") or {}
    positive_windows = sum(
        1
        for window in WINDOWS
        if float((by_window.get(window) or {}).get("total_pnl") or 0.0) > 0.0
    )
    ev_delta = delta.get("expected_value_score")
    pnl_delta = delta.get("total_pnl")
    control_ev = control.get("expected_value_score")
    control_pnl = control.get("total_pnl")
    ev_delta_pct = (
        float(ev_delta) / abs(float(control_ev))
        if isinstance(ev_delta, (int, float))
        and isinstance(control_ev, (int, float))
        and control_ev
        else None
    )
    pnl_delta_pct = (
        float(pnl_delta) / abs(float(control_pnl))
        if isinstance(pnl_delta, (int, float))
        and isinstance(control_pnl, (int, float))
        and control_pnl
        else None
    )
    return bool(
        sleeve.get("trade_count", 0) >= 10
        and positive_windows == len(WINDOWS)
        and isinstance(ev_delta_pct, float)
        and ev_delta_pct > 0.10
        and isinstance(pnl_delta_pct, float)
        and pnl_delta_pct > 0.05
        and (sleeve.get("max_drawdown_pct") or 1.0) <= (control.get("max_drawdown_pct") or 0.0)
    )


def _build_payload() -> dict[str, Any]:
    baseline_metrics, price_map, coverage, candidates = _collect_primary_candidates()
    for candidate in candidates:
        candidate["leadership_item_semantic"] = _item_semantic(candidate)

    variants = _run_variants(candidates, price_map)
    control = variants["all_leadership_negative_reaction"]["sleeve_metrics"]
    best_name = _best_variant(variants)
    best = variants[best_name]
    accepted = _accepted(best, control)
    decision = "rejected_semantic_discriminator_not_promoted"
    if accepted:
        decision = "accepted_requires_shared_default_off_queue_semantic"

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "alpha_category": "event_source_candidate_quality",
        "decision": decision,
        "status": decision,
        "hypothesis": (
            "Inside the frozen SEC leadership-change negative-reaction branch, Item 5.02 "
            "rows with cleaner item-code context may retain rebound alpha while avoiding "
            "mixed governance/procedural rows that hurt the fixed-notional sleeve."
        ),
        "alpha_hypothesis": {
            "entry_exit_ranking_or_sizing": "candidate_pool / event-source quality",
            "why_this_now": (
                "LLM soft-ranking and event bundle live promotion are forward-sample limited; "
                "this tests a replayable SEC semantic discriminator already present in PIT-safe events."
            ),
            "why_not_data_blocked": (
                "The needed fields, eight_k_item_codes and reaction_excess_return, already exist "
                "in data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl and are replayed "
                "across all three canonical OHLCV snapshots."
            ),
        },
        "history_check": {
            "similar_prior_results": {
                "exp-20260504-015": "leadership-change negative-reaction was shadow-promising by forward excess return",
                "exp-20260504-026": "the all-leadership fixed-notional sleeve was rejected because old_thin stayed negative",
                "exp-20260505-008": "leadership queue is observe-only; no live trading promotion before closed paper outcomes",
            },
            "why_not_simple_repeat": (
                "This does not retune the reaction threshold or rerun the same sleeve unchanged; "
                "it keeps the branch frozen and changes only the item-code semantic inclusion set."
            ),
            "mechanism_insight_guardrails": [
                "No core A/B threshold, sizing, ranking, gap-cancel, add-on, or exit rule changed.",
                "No direct event-bundle source insertion before forward outcomes.",
                "No LLM soft-ranking dependency.",
                "No production order path change.",
            ],
        },
        "parameters": {
            "single_causal_variable": "leadership Item 5.02 item-code semantic inclusion",
            "control": "all_leadership_negative_reaction",
            "variants": {name: spec for name, spec in VARIANTS.items()},
            "entry": "next trading-day open after the reaction close",
            "exit": "10 trading-day horizon close",
            "notional": "inherited from exp-20260504-026 fixed leadership sleeve",
            "locked": [
                "reaction bucket <= -2% excess",
                "filing_category == leadership_change",
                "production universe",
                "core A/B backtester behavior",
                "candidate ranking",
                "sizing",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_range": {
            label: {
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
            }
            for label, cfg in WINDOWS.items()
        },
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "core_expected_value_score_delta": {label: 0.0 for label in WINDOWS},
        "control_sleeve_metrics": control,
        "variant_results": variants,
        "best_variant": best_name,
        "best_variant_delta_vs_control": best["delta_vs_all_leadership"],
        "gate4": {
            "core_strategy_applicable": False,
            "reason": "No promoted strategy logic changed; core before/after metrics are unchanged by design.",
            "semantic_sleeve_acceptance": accepted,
            "acceptance_rule": (
                "Best semantic variant must improve the prior all-leadership sleeve by >10% EV "
                "and >5% PnL, keep drawdown no worse, take at least 10 trades, and be profitable "
                "in all three canonical windows."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_signal_generation": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "note": "This deliberately avoids the current LLM soft-ranking coverage bottleneck.",
        },
        "coverage": coverage,
        "candidate_semantic_summary": _candidate_summary(candidates),
        "decision_rationale": (
            "Rejected: the best item-code discriminator improved aggregate sleeve EV/PnL versus "
            "the rejected all-leadership sleeve, but it still failed promotion quality because the "
            "trade count stayed below 10 and the variant did not produce positive PnL in all three "
            "canonical windows."
            if not accepted
            else "Accepted only as a default-off semantic field candidate; promotion still requires shared queue policy and parity tests."
        ),
        "next_retry_requires": (
            "Do not retry nearby item-code inclusion/exclusion on the same frozen sample. A valid "
            "retry needs forward leadership queue paper outcomes, full 5.02 filing text/LLM semantics, "
            "or a closed replacement-value sample versus frozen A/B alternatives."
        ),
        "intentionally_unchanged": [
            "Core trend/breakout/earnings signal logic",
            "Risk sizing and caps",
            "Entry gap cancels",
            "Add-on and exit lifecycle rules",
            "Universe membership",
            "LLM/news veto boundaries",
        ],
        "primary_risk": (
            "A too-narrow event semantic can discard sparse but real rebounds, especially because "
            "leadership-event samples are still small and source-specific."
        ),
    }
    return _safe(payload)


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["best_variant"]
    best_row = payload["variant_results"][best]
    delta = best_row["delta_vs_all_leadership"]
    sleeve = best_row["sleeve_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Leadership Item-Code Semantics",
        "",
        f"- decision: `{payload['decision']}`",
        f"- best variant: `{best}`",
        f"- delta vs all-leadership sleeve EV: {delta.get('expected_value_score')}",
        f"- delta vs all-leadership sleeve PnL: {delta.get('total_pnl')}",
        f"- best variant trades: {sleeve.get('trade_count')}",
        f"- best variant PnL: {sleeve.get('total_pnl')}",
        f"- best variant max drawdown: {sleeve.get('max_drawdown_pct')}",
        "- production impact: `replay_only_no_order_path_change`",
        "",
        "## Window PnL",
        "",
        "| variant | late_strong | mid_weak | old_thin | total |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, row in payload["variant_results"].items():
        summary = (row["sleeve_metrics"].get("trade_summary") or {}).get("by_window") or {}
        values = [float((summary.get(label) or {}).get("total_pnl") or 0.0) for label in WINDOWS]
        lines.append(
            f"| {name} | {values[0]:.2f} | {values[1]:.2f} | {values[2]:.2f} | {sum(values):.2f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["decision_rationale"],
            "",
            "This is alpha search on an event candidate-source discriminator. It does not alter "
            "production entries, ranking, sizing, exits, universe membership, or core backtest behavior.",
            "",
            "## Repro",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe quant\\experiments\\exp_20260505_030_sec_leadership_item_code_semantics.py",
            "```",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC leadership semantic discriminator rejected",
        "status": payload["decision"],
        "summary": payload["decision_rationale"],
        "best_variant": payload["best_variant"],
        "production_impact": payload["production_impact"],
        "next_action": payload["next_retry_requires"],
    }
    _write_json(TICKET_JSON, ticket)


def main() -> int:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_artifact(payload)
    _write_ticket(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "best_variant_delta_vs_control": payload["best_variant_delta_vs_control"],
                "best_variant_metrics": {
                    key: payload["variant_results"][payload["best_variant"]]["sleeve_metrics"][key]
                    for key in (
                        "trade_count",
                        "total_pnl",
                        "expected_value_score",
                        "sharpe_daily",
                        "max_drawdown_pct",
                        "win_rate",
                    )
                },
                "production_impact": payload["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
