"""exp-20260517-022: rotation state-surface active-capacity sweep.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
the maximum number of active rotation-only state-surface paper positions after
the accepted ret20_excess_spy >= 0.0 gate. Core A/B signals, ranking, sizing,
exits, LLM/news, event bundle definitions, and live orders are unchanged.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260517-022"
EXPERIMENT_SLUG = "state_surface_rotation_capacity"
TARGET_SURFACE = "rotation_breakout_leadership"
BASELINE_MAX_ACTIVE_POSITIONS = 3
MAX_ACTIVE_POSITION_VARIANTS = [1, 2, 3, 4, 5, 6]

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260517_014_state_surface_rotation_only_replay as parent  # noqa: E402
from experiments import exp_20260517_017_state_surface_rotation_ret20_excess_iwm_floor as prev  # noqa: E402


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
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
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


def _capacity_label(max_active_positions: int) -> str:
    suffix = "identity" if max_active_positions == BASELINE_MAX_ACTIVE_POSITIONS else "variant"
    return f"{max_active_positions}_active_{suffix}"


def _select_trades_with_capacity(
    candidates: list[dict[str, Any]],
    *,
    max_active_positions: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready = [row for row in candidates if row.get("status") == "price_ready"]
    ready.sort(
        key=lambda row: (
            str(row.get("decision_date") or row.get("date") or ""),
            int(row.get("rank") or 99),
            -float(row.get("score") or 0.0),
            str(row.get("ticker") or ""),
        )
    )

    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = [
        {
            "ticker": row.get("ticker"),
            "decision_date": row.get("date"),
            "reason": row.get("status"),
        }
        for row in candidates
        if row.get("status") != "price_ready"
    ]
    active: list[dict[str, Any]] = []
    for row in ready:
        entry_date = str(row["entry_date"])
        active = [trade for trade in active if str(trade["exit_date"]) >= entry_date]
        active_tickers = {str(trade.get("ticker") or "").upper() for trade in active}
        if len(active) >= max_active_positions:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "decision_date": row.get("decision_date"),
                    "entry_date": entry_date,
                    "reason": "surface_sleeve_capacity_full",
                    "active_tickers": sorted(active_tickers),
                    "max_active_positions": max_active_positions,
                }
            )
            continue
        if str(row.get("ticker") or "").upper() in active_tickers:
            skipped.append(
                {
                    "ticker": row.get("ticker"),
                    "decision_date": row.get("decision_date"),
                    "entry_date": entry_date,
                    "reason": "ticker_already_active",
                    "active_tickers": sorted(active_tickers),
                    "max_active_positions": max_active_positions,
                }
            )
            continue
        selected.append({**row, "max_active_positions": max_active_positions})
        active.append(row)
    return selected, skipped


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
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
                "max_active_positions": trade.get("max_active_positions"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for trade in positive:
        by_ticker[str(trade.get("ticker") or "").upper()] += float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 6) if by_ticker else None


def _variant_payload(
    *,
    max_active_positions: int,
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
        selected, selection_skipped = _select_trades_with_capacity(
            spy_filtered,
            max_active_positions=max_active_positions,
        )
        event_curve = parent.base._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        result = core_results[label]
        after_metrics[label] = parent.base._combined_metrics(result, event_curve, selected)
        selected_all.extend({**trade, "window": label} for trade in selected)
        skipped_reason_counts = Counter(
            str(row.get("reason") or "unknown")
            for row in [*spy_blocked, *selection_skipped]
        )
        surface_sleeve[label] = {
            "raw_rotation_candidate_count": len(candidates),
            "price_ready_rotation_candidate_count": sum(
                1 for row in candidates if row.get("status") == "price_ready"
            ),
            "ret20_excess_spy_blocked_price_ready_count": sum(
                1 for row in spy_blocked if row.get("status") == "price_ready"
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
            "skipped_reason_counts": dict(skipped_reason_counts),
            "capacity_full_skip_count": int(skipped_reason_counts.get("surface_sleeve_capacity_full", 0)),
            "selected_trades": _selected_trade_rows(selected),
        }

    return {
        "max_active_positions": max_active_positions,
        "capacity_label": _capacity_label(max_active_positions),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trade_count": len(selected_all),
        "single_ticker_positive_share": _single_ticker_positive_share(selected_all),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Rotation Capacity",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `max_active_surface_positions` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Max active | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {cap} | {passed} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {trades} | {dd:+.4f} | {share} |".format(
                cap=row["max_active_positions"],
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                trades=row["selected_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share="n/a" if share is None else f"{share:.2%}",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades | Capacity skips |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} | {trades} | {skips} |".format(
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
                skips=sleeve["capacity_full_skip_count"],
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
            max_active_positions=max_active_positions,
            core_results=core_results,
            rotation_candidates_by_window=rotation_candidates_by_window,
            prices=prices,
        )
        for max_active_positions in MAX_ACTIVE_POSITION_VARIANTS
    ]
    baseline = next(
        row for row in variants if row["max_active_positions"] == BASELINE_MAX_ACTIVE_POSITIONS
    )
    baseline_metrics = baseline["metrics"]
    sweep_summary = []
    for variant in variants:
        gate4 = prev._gate4_for_variant(
            baseline_metrics=baseline_metrics,
            variant=variant,
        )
        sweep_summary.append(
            {
                "max_active_positions": variant["max_active_positions"],
                "capacity_label": variant["capacity_label"],
                "is_identity_control": (
                    variant["max_active_positions"] == BASELINE_MAX_ACTIVE_POSITIONS
                ),
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
            row["selected_trade_count"],
        ),
    )
    best_variant = next(
        row
        for row in variants
        if row["max_active_positions"] == best_summary["max_active_positions"]
    )
    delta = best_summary["gate4"]["delta_metrics"]

    if best_summary["gate4"]["passed"]:
        decision = "passed_replay_requires_shared_capacity_policy"
        status = "pending_promotion"
        interpretation = (
            "A different active-position cap improved the accepted rotation-only "
            "state-surface paper sleeve. Promotion requires updating shared "
            "state_surface_sleeve.py and parity tests before this can become accepted "
            "default-off production policy."
        )
    else:
        decision = "rejected_state_surface_capacity_sweep"
        status = "rejected"
        interpretation = (
            "No tested active-position cap improved the accepted rotation-only "
            "state-surface paper sleeve across the three fixed windows after locking "
            "the accepted ret20_excess_spy gate."
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rotation_active_capacity",
        "changed_variable": "max_active_surface_positions",
        "change_summary": (
            "Sweep the active-position cap for accepted rotation-only state-surface "
            "paper candidates after the accepted ret20_excess_spy gate."
        ),
        "component": "quant/experiments",
        "mechanism_family": "state_aware_candidate_pool_capacity",
        "hypothesis": (
            "Within the accepted rotation_breakout_leadership state-surface paper sleeve, "
            "the current max-3 active cap may either under-allocate concurrent high-quality "
            "rotation candidates or admit too much overlap. A one-variable cap sweep can "
            "measure whether replacement value improves without adding tickers, changing "
            "candidate scoring, or touching live orders."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension",
            "entry_exit_ranking_or_allocation": "satellite paper capacity allocation",
            "playbook_alignment": (
                "Targets the playbook's event-rotation replacement-value lane and current "
                "ticker-pool governance. It avoids LLM soft-ranking, SEC semantic sample "
                "limits, nearby ret20/ret60/near-high/volume thresholds, and noisy ticker expansion."
            ),
        },
        "history_check": {
            "exp-20260517-014": "Accepted rotation-only state-surface paper eligibility.",
            "exp-20260517-016": "Accepted candidate-level SPY-relative 20d excess floor.",
            "exp-20260517-017": "Rejected candidate-level IWM-relative 20d excess floor.",
            "exp-20260517-019": "Rejected candidate-level ret60 floor.",
            "exp-20260517-020": "Rejected candidate-level near_high_60 floor.",
            "exp-20260517-021": "Rejected volume_ratio_20 floor; only mid_weak improved.",
            "anti_repeat_boundary": (
                "This does not retune ret20_excess_spy, IWM, ret60, near-high, or volume "
                "thresholds, does not add tickers, and does not change paper notional."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate-pool/capital-allocation alpha: ret20-spy-gated rotation-only "
                "state-surface paper candidates may have better replacement value with a "
                "different active-position cap than the current max-3 cap"
            ),
            "2_history_check": (
                "Rotation-only, 20-day SPY/IWM relative gates, ret60 floor, near_high_60 "
                "floor, and volume_ratio_20 floor were tested. No current-stack ret20-spy-"
                "gated state-surface active-capacity experiment was found."
            ),
            "3_single_causal_variable": "max_active_surface_positions",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control cap must improve "
                "aggregate EV/PnL versus current accepted max-3 ret20-spy-gated control, "
                f"improve at least two windows, regress zero windows, keep selected trades >= {prev.MIN_SELECTED_TRADES}, "
                f"max drawdown drift <= {prev.MAX_DRAWDOWN_WORSE:.1%}, and single-ticker positive "
                f"share <= {prev.MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260517_022_state_surface_rotation_capacity.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "max_active_surface_positions",
            "baseline_max_active_positions": BASELINE_MAX_ACTIVE_POSITIONS,
            "max_active_position_variants": MAX_ACTIVE_POSITION_VARIANTS,
            "best_max_active_positions": best_summary["max_active_positions"],
            "locked_ret20_excess_spy_min": 0.0,
            "allowed_surfaces_locked": [TARGET_SURFACE],
            "decision_timing": "score after decision-date close; enter next trading day open",
            "candidate_source": "production universe only, excluding SPY/QQQ/IWM and existing same-day core candidates",
            "daily_candidate_count_source": parent.base.DAILY_CANDIDATE_COUNT,
            "hold_days": parent.base.HOLD_DAYS,
            "event_notional_usd": parent.base.EVENT_NOTIONAL,
            "locked_variables": [
                "core universe files",
                "signal generation",
                "entry filters",
                "candidate scoring",
                "candidate daily rank count",
                "risk sizing",
                "core position slots",
                "gap cancels",
                "add-ons",
                "exits",
                "LLM/news replay",
                "event bundle source definitions",
                "event bundle notional/scalars",
                "production orders",
                "state-surface allowed surface",
                "state-surface benchmark momentum gate",
                "state-surface ret20_excess_spy gate",
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
            "baseline_max_active_positions": BASELINE_MAX_ACTIVE_POSITIONS,
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
                "This run is a replay-only alpha scout. If Gate 4 passes, the active "
                "cap must be promoted in shared state_surface_sleeve.py with parity "
                "tests before acceptance. Live/default orders remain disabled."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft-ranking data remains sparse/PIT-limited; this deterministic "
                "state-surface paper capacity test uses only replayable OHLCV fields."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if best_summary["gate4"]["passed"] else interpretation,
        "next_evidence_needed": (
            "Implement the new active cap in shared state_surface_sleeve.py and rerun parity tests before acceptance."
            if best_summary["gate4"]["passed"]
            else "Do not change the state-surface active cap on frozen windows; next rotation search needs a different production-visible discriminator or forward replacement-value evidence."
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
            "title": "State-surface rotation active capacity",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_max_active_positions": payload["parameters"]["best_max_active_positions"],
            "expected_value_score_delta": payload["delta_metrics"]["aggregate_ev_delta"],
            "total_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
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
                    "best_max_active_positions": payload["parameters"]["best_max_active_positions"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "windows_ev_improved": payload["gate4"]["windows_ev_improved"],
                    "windows_ev_regressed": payload["gate4"]["windows_ev_regressed"],
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
