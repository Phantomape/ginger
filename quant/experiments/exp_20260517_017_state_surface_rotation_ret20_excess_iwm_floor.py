"""exp-20260517-017: rotation state-surface ret20 excess IWM floor.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
the minimum 20-day return excess versus IWM required before accepted
rotation-only state-surface candidates enter the paper ledger. Core A/B
signals, ranking, sizing, exits, event bundle logic, LLM/news, and live orders
are unchanged.

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


EXPERIMENT_ID = "exp-20260517-017"
EXPERIMENT_SLUG = "state_surface_rotation_ret20_excess_iwm_floor"
TARGET_SURFACE = "rotation_breakout_leadership"
BASELINE_FLOOR: float | None = None
FLOOR_VARIANTS: list[float | None] = [None, 0.0, 0.025, 0.05, 0.075, 0.10, 0.15]
MIN_SELECTED_TRADES = 9
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50
MAX_DRAWDOWN_WORSE = 0.005

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260517_014_state_surface_rotation_only_replay as parent  # noqa: E402
from state_surface_sleeve import evaluate_ret20_excess_spy_gate  # noqa: E402


WINDOWS = parent.WINDOWS
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
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


def _floor_label(floor: float | None) -> str:
    return "identity_no_iwm_floor" if floor is None else f"{floor:.2%}"


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _round(value: Any, digits: int = 6) -> Any:
    parsed = _float_or_none(value)
    return round(parsed, digits) if parsed is not None else None


def _ret20(prices: dict[str, list[dict[str, Any]]], ticker: str, date_str: str) -> float | None:
    rows = [row for row in prices.get(str(ticker).upper(), []) if str(row.get("date") or "") <= date_str]
    if len(rows) <= 20:
        return None
    now = _float_or_none(rows[-1].get("close"))
    then = _float_or_none(rows[-21].get("close"))
    if not now or not then:
        return None
    return now / then - 1.0


def _ret20_iwm_gate(
    row: dict[str, Any],
    *,
    floor: float | None,
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    date_str = str(row.get("decision_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    ticker_ret20 = _ret20(prices, ticker, date_str)
    iwm_ret20 = _ret20(prices, "IWM", date_str)
    excess = None if ticker_ret20 is None or iwm_ret20 is None else ticker_ret20 - iwm_ret20
    enabled = floor is not None
    reasons: list[str] = []
    if enabled:
        if excess is None:
            reasons.append("ret20_excess_iwm_unavailable")
        elif excess < float(floor):
            reasons.append("ret20_excess_iwm_below_floor")
    allowed = (not enabled) or not reasons
    return {
        "rule_version": "state_surface_ret20_excess_iwm_gate_replay_v1",
        "enabled": enabled,
        "identity_control": floor is None,
        "allowed": allowed,
        "status": "allowed" if allowed else "blocked",
        "reasons": reasons,
        "ret20": _round(ticker_ret20),
        "iwm_ret20": _round(iwm_ret20),
        "ret20_excess_iwm": _round(excess),
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


def _apply_locked_spy_floor(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept = []
    blocked = []
    for row in candidates:
        if row.get("status") != "price_ready":
            kept.append(row)
            continue
        gate = evaluate_ret20_excess_spy_gate(
            row,
            {"ret20_excess_spy_gate_enabled": True, "ret20_excess_spy_min": 0.0},
        )
        enriched = {**row, "ret20_excess_spy_gate": gate}
        if gate["allowed"]:
            kept.append(enriched)
        else:
            blocked.append({**enriched, "reason": "ret20_excess_spy_gate_blocked"})
    return kept, blocked


def _filter_by_floor(
    candidates: list[dict[str, Any]],
    *,
    floor: float | None,
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept = []
    blocked = []
    for row in candidates:
        if row.get("status") != "price_ready":
            kept.append(row)
            continue
        gate = _ret20_iwm_gate(row, floor=floor, prices=prices)
        enriched = {**row, "ret20_excess_iwm_gate": gate}
        if gate["allowed"]:
            kept.append(enriched)
        else:
            blocked.append({**enriched, "reason": "ret20_excess_iwm_gate_blocked"})
    return kept, blocked


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for trade in positive:
        by_ticker[str(trade.get("ticker") or "").upper()] += float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 6) if by_ticker else None


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        features = trade.get("features") or {}
        gate = trade.get("ret20_excess_iwm_gate") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "score": trade.get("score"),
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret20_excess_iwm": gate.get("ret20_excess_iwm"),
                "ret20_excess_iwm_gate_allowed": gate.get("allowed"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


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
        spy_filtered, spy_blocked = _apply_locked_spy_floor(candidates)
        filtered, iwm_blocked = _filter_by_floor(spy_filtered, floor=floor, prices=prices)
        gate_blocked = [*spy_blocked, *iwm_blocked]
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

    selected_count = len(selected_all)
    positive_share = _single_ticker_positive_share(selected_all)
    return {
        "floor": floor,
        "floor_label": _floor_label(floor),
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trade_count": selected_count,
        "single_ticker_positive_share": positive_share,
    }


def _gate4_for_variant(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    variant: dict[str, Any],
) -> dict[str, Any]:
    after_metrics = variant["metrics"]
    delta = parent._aggregate_delta(baseline_metrics, after_metrics)
    by_window = OrderedDict(
        (label, parent.base._gate4(baseline_metrics[label], after_metrics[label]))
        for label in WINDOWS
    )
    sample_guard_passed = variant["selected_trade_count"] >= MIN_SELECTED_TRADES
    concentration_guard_passed = (
        variant["single_ticker_positive_share"] is None
        or variant["single_ticker_positive_share"] <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= MAX_DRAWDOWN_WORSE
    passed = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and sample_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    return {
        "passed": passed,
        "by_window": by_window,
        "aggregate_ev_delta": delta["aggregate_ev_delta"],
        "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
        "windows_ev_improved": delta["windows_ev_improved"],
        "windows_ev_regressed": delta["windows_ev_regressed"],
        "selected_trade_count": variant["selected_trade_count"],
        "minimum_selected_trades": MIN_SELECTED_TRADES,
        "sample_guard_passed": sample_guard_passed,
        "single_ticker_positive_share": variant["single_ticker_positive_share"],
        "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
        "concentration_guard_passed": concentration_guard_passed,
        "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "drawdown_guard_passed": drawdown_guard_passed,
        "delta_metrics": delta,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} State-Surface Rotation Ret20 Excess IWM Floor",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `ret20_excess_iwm_min` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Floor | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {floor} | {passed} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {trades} | {dd:+.4f} | {share} |".format(
                floor=_floor_label(row["floor"]),
                passed="PASS" if row["gate4"]["passed"] else "FAIL",
                ev=row["gate4"]["aggregate_ev_delta"],
                pnl=row["gate4"]["aggregate_pnl_delta"],
                wi=row["gate4"]["windows_ev_improved"],
                wr=row["gate4"]["windows_ev_regressed"],
                trades=row["selected_trade_count"],
                dd=row["gate4"]["max_drawdown_worse_max"],
                share="" if share is None else f"{share:.2%}",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Best Variant",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bdd:.2%} | {add:.2%} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
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
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    gate2 = parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
    baseline_variant = next(row for row in variants if row["floor"] is BASELINE_FLOOR)
    baseline_metrics = baseline_variant["metrics"]

    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            variant=variant,
        )
        sweep_summary.append(
            {
                "floor": variant["floor"],
                "floor_label": variant["floor_label"],
                "is_identity_control": variant["floor"] is BASELINE_FLOOR,
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
            row["selected_trade_count"],
            -(float(row["floor"]) if row["floor"] is not None else 999.0),
        ),
    )
    best_variant = next(row for row in variants if row["floor"] == best_summary["floor"])
    decision = (
        "accepted_shared_default_off_policy_ret20_excess_iwm_floor"
        if best_summary["gate4"]["passed"]
        else "rejected_state_surface_ret20_excess_iwm_floor"
    )
    interpretation = (
        "A nonnegative 20-day return excess versus IWM improved the default-off rotation state-surface paper sleeve while preserving the three-window guards."
        if best_summary["gate4"]["passed"]
        else "No tested 20-day IWM-relative excess floor cleared the three-window gate versus the identity control."
    )
    delta = best_summary["gate4"]["delta_metrics"]

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rotation_ret20_excess_iwm_floor",
        "mechanism_family": "state_aware_candidate_pool_extension",
        "hypothesis": (
            "Within the accepted rotation_breakout_leadership state-surface paper sleeve, "
            "a candidate should beat the small-cap/broad-rotation benchmark it is trying "
            "to exploit. A nonnegative ret20_excess_iwm floor may improve replacement "
            "value without expanding the candidate universe or changing core logic."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension",
            "entry_exit_ranking_or_allocation": "satellite paper candidate eligibility",
            "playbook_alignment": (
                "Uses the current event/state rotation lane, adds one replayable "
                "production-visible field candidate, avoids LLM/SEC data limits, "
                "and improves candidate-pool quality rather than adding noisy tickers."
            ),
        },
        "historical_experiment_check": {
            "exp-20260517-014": "Accepted rotation-only state-surface paper eligibility.",
            "exp-20260517-015": "Rejected stricter benchmark participation gates.",
            "exp-20260517-016": (
                "Accepted candidate-level SPY-relative 20d excess floor. This run "
                "does not retune that floor; it tests IWM-relative excess as a new "
                "rotation-specific quality discriminator."
            ),
            "anti_repeat_boundary": (
                "This is not a nearby ret20_excess_spy threshold retry, not a notional "
                "sweep, not a hold-day sweep, and not live capital promotion."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool alpha: require positive 20-day excess return versus IWM "
                "for rotation-only state-surface paper candidates"
            ),
            "2_history_check": (
                "Rotation-only and SPY-relative candidate quality were tested; IWM-relative "
                "candidate quality has not been tested on the current stack."
            ),
            "3_single_causal_variable": "ret20_excess_iwm_min",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control floor must "
                "improve aggregate EV/PnL versus identity, improve at least two windows, "
                "regress zero windows, keep selected trades >= "
                f"{MIN_SELECTED_TRADES}, max drawdown drift <= {MAX_DRAWDOWN_WORSE:.1%}, "
                f"and single-ticker positive share <= {MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260517_017_state_surface_rotation_ret20_excess_iwm_floor.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "ret20_excess_iwm_min",
            "baseline_floor": BASELINE_FLOOR,
            "floor_variants": FLOOR_VARIANTS,
            "best_floor": best_summary["floor"],
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
            "current_state_surface_no_iwm_floor_baseline_metrics": baseline_metrics,
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
                "OHLCV IWM ret20",
                "OHLCV ticker ret20",
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
            "promotion_blocker_if_positive": (
                "A passing result would require adding ret20_excess_iwm as a shared "
                "default-off paper policy field plus run/backtester parity tests before "
                "retention."
            ),
            "production_impact": (
                "Replay-only alpha scout; no shared policy is changed unless Gate 4 "
                "passes and a separate shared default-off policy patch is applied."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft-ranking data remains sparse/PIT-limited; this deterministic "
                "state-surface paper gate uses replayable OHLCV fields."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if best_summary["gate4"]["passed"] else interpretation,
        "next_evidence_needed": (
            "If retained, implement the IWM-relative field in shared state_surface_sleeve.py and rerun parity tests."
            if best_summary["gate4"]["passed"]
            else "Avoid IWM-relative floors on frozen windows; look for a different production-visible state field."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            "quant/state_surface_sleeve.py",
            "quant/test_state_surface_sleeve.py",
            "docs/production_backtest_parity.md",
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rotation ret20 excess IWM floor",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_floor": payload["parameters"]["best_floor"],
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
                    "best_floor": payload["parameters"]["best_floor"],
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
