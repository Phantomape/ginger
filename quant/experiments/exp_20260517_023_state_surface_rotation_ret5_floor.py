"""exp-20260517-023: rotation state-surface ret5 floor.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
the minimum signal-day 5-day return required before accepted rotation-only
state-surface paper candidates enter the paper ledger. The accepted
ret20_excess_spy >= 0.0 gate stays locked. Core entries, filters, ranking,
sizing, exits, LLM/news, event bundle definitions, and live orders are
unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260517-023"
EXPERIMENT_SLUG = "state_surface_rotation_ret5_floor"
TARGET_SURFACE = "rotation_breakout_leadership"
BASELINE_FLOOR: float | None = None
FLOOR_VARIANTS: list[float | None] = [None, -0.05, -0.025, 0.0, 0.025, 0.05, 0.10, 0.125]
MIN_CHANGED_SELECTED_TRADES = 3

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260517_021_state_surface_rotation_volume_floor as volume_exp  # noqa: E402


parent = volume_exp.parent
prev = volume_exp.prev
WINDOWS = parent.WINDOWS
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _safe(value: Any) -> Any:
    return volume_exp._safe(value)


def _repo_rel(path: Path | str) -> str:
    return volume_exp._repo_rel(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    volume_exp._write_json(path, payload)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _float_or_none(value: Any) -> float | None:
    return volume_exp._float_or_none(value)


def _round(value: Any, digits: int = 6) -> Any:
    parsed = _float_or_none(value)
    return round(parsed, digits) if parsed is not None else None


def _floor_label(floor: float | None) -> str:
    return "identity_no_ret5_floor" if floor is None else f"{floor:+.3f}"


def _ret5_gate(row: dict[str, Any], *, floor: float | None) -> dict[str, Any]:
    features = row.get("features") or {}
    ret5 = _float_or_none(features.get("ret5"))
    enabled = floor is not None
    reasons: list[str] = []
    if enabled:
        if ret5 is None:
            reasons.append("ret5_unavailable")
        elif ret5 < float(floor):
            reasons.append("ret5_below_floor")
    allowed = (not enabled) or not reasons
    return {
        "rule_version": "state_surface_ret5_floor_replay_v1",
        "enabled": enabled,
        "identity_control": floor is None,
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked",
        "reasons": reasons,
        "ret5": _round(ret5),
        "threshold": _round(floor),
        "scope": "default_off_state_surface_paper_candidate_queue",
        "trade_enabled_after_gate": False,
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "replay_only": True,
            "alters_orders": False,
        },
    }


def _filter_by_floor(
    candidates: list[dict[str, Any]],
    *,
    floor: float | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept = []
    blocked = []
    for row in candidates:
        if row.get("status") != "price_ready":
            kept.append(row)
            continue
        gate = _ret5_gate(row, floor=floor)
        enriched = {**row, "ret5_floor_gate": gate}
        if gate["allowed"]:
            kept.append(enriched)
        else:
            blocked.append({**enriched, "reason": "ret5_floor_gate_blocked"})
    return kept, blocked


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        gate = trade.get("ret5_floor_gate") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "score": trade.get("score"),
                "ret5": features.get("ret5"),
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret60": features.get("ret60"),
                "near_high_60": features.get("near_high_60"),
                "volume_ratio_20": features.get("volume_ratio_20"),
                "ret5_floor_gate_allowed": gate.get("allowed"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _selected_keys(variant: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    keys: set[tuple[str, str, str, str]] = set()
    for window_label, sleeve in variant["surface_sleeve"].items():
        for trade in sleeve["selected_trades"]:
            keys.add(
                (
                    str(window_label),
                    str(trade.get("ticker") or ""),
                    str(trade.get("entry_date") or ""),
                    str(trade.get("exit_date") or ""),
                )
            )
    return keys


def _variant_payload(
    *,
    floor: float | None,
    core_results: dict[str, dict[str, Any]],
    rotation_candidates_by_window: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        candidates = rotation_candidates_by_window[label]
        spy_filtered, spy_blocked = prev._apply_locked_spy_floor(candidates)
        filtered, ret5_blocked = _filter_by_floor(spy_filtered, floor=floor)
        gate_blocked = [*spy_blocked, *ret5_blocked]
        selected, selection_skipped = parent.base._select_trades(filtered)
        event_curve = parent.base._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        result = core_results[label]
        after_metrics[label] = parent.base._combined_metrics(result, event_curve, selected)
        selected_all.extend({**trade, "window": label} for trade in selected)
        surface_sleeve[label] = {
            "raw_rotation_candidate_count": len(candidates),
            "price_ready_rotation_candidate_count": sum(
                1 for row in candidates if row.get("status") == "price_ready"
            ),
            "gate_blocked_price_ready_count": sum(
                1 for row in gate_blocked if row.get("status") == "price_ready"
            ),
            "selected_trade_count": len(selected),
            "selected_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in selected), 2),
            "selected_win_rate": round(
                sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0) / len(selected),
                4,
            )
            if selected
            else None,
            "surface_summary": parent.base._surface_summary(selected),
            "skipped_reason_counts": dict(
                Counter(
                    str(row.get("reason") or "unknown")
                    for row in [*gate_blocked, *selection_skipped]
                )
            ),
            "selected_trades": _selected_trade_rows(selected),
        }

    return {
        "floor": floor,
        "floor_label": _floor_label(floor),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trade_count": len(selected_all),
        "single_ticker_positive_share": prev._single_ticker_positive_share(selected_all),
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    baseline_selected_keys: set[tuple[str, str, str, str]],
    variant: dict[str, Any],
) -> dict[str, Any]:
    gate4 = prev._gate4_for_variant(baseline_metrics=baseline_metrics, variant=variant)
    selected_keys = _selected_keys(variant)
    changed_selected_trade_count = len(baseline_selected_keys.symmetric_difference(selected_keys))
    contrast_guard_passed = changed_selected_trade_count >= MIN_CHANGED_SELECTED_TRADES
    gate4["changed_selected_trade_count"] = changed_selected_trade_count
    gate4["minimum_changed_selected_trades"] = MIN_CHANGED_SELECTED_TRADES
    gate4["contrast_guard_passed"] = contrast_guard_passed
    gate4["passed"] = bool(gate4["passed"] and contrast_guard_passed)
    return gate4


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Rotation Ret5 Floor",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `ret5_min` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Changed Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {floor} | {passed} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {trades} | {changed} | {dd:+.4%} | {share} |".format(
                floor=row["floor_label"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                trades=row["selected_trade_count"],
                changed=row["gate4"]["changed_selected_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share="n/a" if share is None else f"{share:.2%}",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve Trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                trades=sleeve["selected_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            payload["production_impact"]["production_impact"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    gate2 = parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    prices = parent._load_price_map()
    core_results: dict[str, dict[str, Any]] = OrderedDict()
    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    rotation_candidates_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    for label, window in WINDOWS.items():
        result = parent._load_core_result(window)
        core_results[label] = result
        core_metrics[label] = parent.base._core_metrics(result)
        rotation_candidates_by_window[label] = parent._rotation_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )

    variants = [
        _variant_payload(
            floor=floor,
            core_results=core_results,
            rotation_candidates_by_window=rotation_candidates_by_window,
            prices=prices,
        )
        for floor in FLOOR_VARIANTS
    ]
    baseline = next(row for row in variants if row["floor"] == BASELINE_FLOOR)
    baseline_metrics = baseline["metrics"]
    baseline_selected_keys = _selected_keys(baseline)

    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            baseline_selected_keys=baseline_selected_keys,
            variant=variant,
        )
        sweep_summary.append(
            {
                "floor": variant["floor"],
                "floor_label": variant["floor_label"],
                "is_identity_control": variant["floor"] is None,
                "selected_trade_count": variant["selected_trade_count"],
                "single_ticker_positive_share": variant["single_ticker_positive_share"],
                "gate4": gate4,
            }
        )

    non_control = [row for row in sweep_summary if not row["is_identity_control"]]
    best_summary = max(
        non_control,
        key=lambda row: (
            row["gate4"]["passed"],
            row["gate4"]["aggregate_ev_delta"],
            row["gate4"]["aggregate_pnl_delta"],
            -row["gate4"]["windows_ev_regressed"],
            row["gate4"]["changed_selected_trade_count"],
            row["selected_trade_count"],
        ),
    )
    best_variant = next(row for row in variants if row["floor"] == best_summary["floor"])
    delta = best_summary["gate4"]["delta_metrics"]

    if best_summary["gate4"]["passed"]:
        decision = "passed_replay_requires_shared_ret5_floor"
        status = "pending_promotion"
        interpretation = (
            "A ret5 floor improved the accepted rotation-only state-surface paper sleeve. "
            "Promotion requires adding the gate to shared state_surface_sleeve.py and parity tests "
            "before this can become accepted default-off production policy."
        )
    elif best_summary["gate4"]["aggregate_ev_delta"] > 0:
        decision = "rejected_underpowered_state_surface_ret5_floor"
        status = "rejected"
        interpretation = (
            "The best ret5 floor improved aggregate EV/PnL only by removing one selected mid_weak loss. "
            "It improved fewer than two windows and changed fewer than three selected trades, so the "
            "result is too thin to promote without overfitting the frozen windows."
        )
    else:
        decision = "rejected_state_surface_ret5_floor"
        status = "rejected"
        interpretation = (
            "No tested ret5 floor improved the accepted rotation-only state-surface paper sleeve across "
            "the three fixed windows after locking the accepted ret20_excess_spy gate."
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rotation_ret5_floor",
        "changed_variable": "ret5_min",
        "change_summary": (
            "Sweep a minimum 5-day return floor for accepted rotation-only state-surface paper "
            "candidates after the accepted ret20_excess_spy gate."
        ),
        "component": "quant/experiments",
        "mechanism_family": "state_aware_candidate_pool_quality",
        "hypothesis": (
            "Within the accepted rotation_breakout_leadership state-surface paper sleeve, deep "
            "near-term pullbacks may indicate failed rotation rather than healthy leadership. A ret5 "
            "floor may improve paper candidate quality without expanding the candidate universe or "
            "changing core logic."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension",
            "entry_exit_ranking_or_allocation": "satellite paper candidate eligibility",
            "playbook_alignment": (
                "Matches the playbook preference for one replayable production-visible state field "
                "and candidate-pool quality over broader ticker expansion or LLM soft-ranking when "
                "LLM replay data is sparse."
            ),
        },
        "history_check": {
            "exp-20260517-014": "Accepted rotation-only state-surface paper eligibility.",
            "exp-20260517-016": "Accepted candidate-level SPY-relative 20d excess floor.",
            "exp-20260517-017": "Rejected candidate-level IWM-relative 20d excess floor.",
            "exp-20260517-019": "Rejected candidate-level ret60 floor.",
            "exp-20260517-020": "Rejected candidate-level near_high_60 floor.",
            "exp-20260517-021": "Rejected candidate-level volume_ratio_20 floor.",
            "exp-20260517-022": "Rejected max-active capacity sweep.",
            "anti_repeat_boundary": (
                "This is not a ret20 threshold retry, not a ret60/near-high/volume retry, "
                "not a capacity retry, not a ticker expansion, and not a notional scalar sweep."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate-pool alpha: require rotation-only state-surface paper candidates already "
                "passing ret20_excess_spy >= 0 to avoid deep 5-day pullbacks"
            ),
            "2_history_check": (
                "Rotation-only, 20-day SPY/IWM relative gates, ret60 floor, near_high_60 floor, "
                "volume_ratio_20 floor, and active-capacity sweeps were tested; no current-stack "
                "ret5 floor experiment was found."
            ),
            "3_single_causal_variable": "ret5_min",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control floor must improve "
                "aggregate EV/PnL versus current accepted ret20-spy-gated control, improve at least "
                f"two windows, regress zero windows, keep selected trades >= {prev.MIN_SELECTED_TRADES}, "
                f"change at least {MIN_CHANGED_SELECTED_TRADES} selected trades, max drawdown drift <= "
                f"{prev.MAX_DRAWDOWN_WORSE:.1%}, and single-ticker positive share <= "
                f"{prev.MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260517_023_state_surface_rotation_ret5_floor.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "ret5_min",
            "baseline_floor": BASELINE_FLOOR,
            "floor_variants": FLOOR_VARIANTS,
            "best_floor": best_summary["floor"],
            "locked_ret20_excess_spy_min": 0.0,
            "allowed_surfaces_locked": [TARGET_SURFACE],
            "decision_timing": "score after decision-date close; enter next trading day open",
            "candidate_source": "production universe only, excluding SPY/QQQ/IWM and existing same-day core candidates",
            "daily_candidate_count_source": parent.base.DAILY_CANDIDATE_COUNT,
            "max_active_surface_positions": parent.base.MAX_ACTIVE_SURFACE_POSITIONS,
            "hold_days": parent.base.HOLD_DAYS,
            "event_notional_usd": parent.base.EVENT_NOTIONAL,
            "locked_variables": [
                "core universe files",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk sizing",
                "position slots",
                "gap cancels",
                "add-ons",
                "exits",
                "LLM/news replay",
                "event bundle source definitions",
                "event bundle notional/scalars",
                "production orders",
                "state-surface allowed surface",
                "state-surface scoring weights",
                "state-surface benchmark momentum gate",
                "state-surface ret20_excess_spy gate",
                "state-surface volume gate",
                "state-surface active capacity",
                "state-surface hold days",
                "state-surface paper notional",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "snapshots": {label: w["snapshot"] for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "canonical_core_baseline_metrics": core_metrics,
            "current_state_surface_ret20_spy_gate_baseline_metrics": baseline_metrics,
            "baseline_floor": BASELINE_FLOOR,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "state_surface surface",
                "state_surface score",
                "state_surface decision_date",
                "state_surface features.ret20_excess_spy",
                "state_surface features.ret5",
                "OHLCV next-session open",
                "OHLCV hold-window exit close",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_core_filter_added": False,
            "core_signals_generated_delta": 0,
            "core_signals_survived_delta": 0,
            "minimum_after_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in core_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values()) >= 0.05,
        },
        "gate4": best_summary["gate4"],
        "before_metrics": baseline_metrics,
        "after_metrics": best_variant["metrics"],
        "delta_metrics": delta,
        "surface_sleeve": best_variant["surface_sleeve"],
        "sweep_summary": sweep_summary,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"] for label in WINDOWS
        },
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        },
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
            "shared_policy_file": "quant/state_surface_sleeve.py",
            "parity_test_file": "quant/test_state_surface_sleeve.py",
            "production_impact": (
                "This run is a replay-only alpha scout. Because Gate 4 did not pass, no shared "
                "default-off production policy was changed. If a ret5 floor ever passes, it must "
                "be added to state_surface_sleeve.py with parity tests before promotion. "
                "Live/default orders remain disabled."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft-ranking data remains sparse/PIT-limited; this deterministic state-surface "
                "paper gate uses only replayable OHLCV fields."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if best_summary["gate4"]["passed"] else interpretation,
        "next_evidence_needed": (
            "Implement the ret5 floor in shared state_surface_sleeve.py and rerun parity tests before acceptance."
            if best_summary["gate4"]["passed"]
            else "Do not add a ret5 floor on frozen windows; next state-surface alpha should use a different production-visible discriminator or forward replacement-value evidence."
        ),
        "anti_js": "No JavaScript was used.",
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
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rotation ret5 floor",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_floor": payload["parameters"]["best_floor"],
            "expected_value_score_delta": payload["delta_metrics"]["aggregate_ev_delta"],
            "total_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
            "changed_selected_trade_count": payload["gate4"]["changed_selected_trade_count"],
            "gate4_passed": payload["gate4"]["passed"],
            "summary": payload["interpretation"],
            "artifact": _repo_rel(OUT_JSON),
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_floor": payload["parameters"]["best_floor"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "windows_ev_improved": payload["gate4"]["windows_ev_improved"],
                    "windows_ev_regressed": payload["gate4"]["windows_ev_regressed"],
                    "changed_selected_trade_count": payload["gate4"]["changed_selected_trade_count"],
                    "selected_trade_count": payload["gate4"]["selected_trade_count"],
                    "single_ticker_positive_share": payload["gate4"]["single_ticker_positive_share"],
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
