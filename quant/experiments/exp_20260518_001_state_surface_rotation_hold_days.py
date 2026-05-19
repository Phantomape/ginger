"""exp-20260518-001: rotation state-surface hold-days sweep.

Alpha search. Tests one production-visible default-off paper-sleeve variable:
the fixed hold horizon for the accepted top-five rotation-only state-surface
paper queue. Core A/B signals, ranking, sizing, exits, LLM/news, event bundle
definitions, active capacity, candidate count, and live orders are unchanged.

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


EXPERIMENT_ID = "exp-20260518-001"
EXPERIMENT_SLUG = "state_surface_rotation_hold_days"
TARGET_SURFACE = "rotation_breakout_leadership"
BASELINE_HOLD_DAYS = 20
ACCEPTED_DAILY_CANDIDATE_COUNT = 5
HOLD_DAY_VARIANTS = [5, 10, 15, 20, 25, 30]

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260517_014_state_surface_rotation_only_replay as parent  # noqa: E402
from experiments import exp_20260517_017_state_surface_rotation_ret20_excess_iwm_floor as spy_gate  # noqa: E402
from experiments import exp_20260517_025_state_surface_rotation_daily_candidate_count as count_exp  # noqa: E402


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

MIN_SELECTED_TRADES = spy_gate.MIN_SELECTED_TRADES
MAX_SINGLE_TICKER_POSITIVE_SHARE = spy_gate.MAX_SINGLE_TICKER_POSITIVE_SHARE
MAX_DRAWDOWN_WORSE = spy_gate.MAX_DRAWDOWN_WORSE


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


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: dict[str, float] = {}
    for trade in positive:
        ticker = str(trade.get("ticker") or "").upper()
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 6) if by_ticker else None


def _rotation_candidates_for_hold_days(
    *,
    hold_days: int,
    label: str,
    window: dict[str, str],
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    original_count = parent.base.DAILY_CANDIDATE_COUNT
    original_hold_days = parent.base.HOLD_DAYS
    parent.base.DAILY_CANDIDATE_COUNT = ACCEPTED_DAILY_CANDIDATE_COUNT
    parent.base.HOLD_DAYS = hold_days
    try:
        return parent._rotation_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
    finally:
        parent.base.DAILY_CANDIDATE_COUNT = original_count
        parent.base.HOLD_DAYS = original_hold_days


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
                "ret20_excess_spy": features.get("ret20_excess_spy"),
                "ret5": features.get("ret5"),
                "ret60": features.get("ret60"),
                "near_high_60": features.get("near_high_60"),
                "volume_ratio_20": features.get("volume_ratio_20"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _variant_payload(
    *,
    hold_days: int,
    core_results: dict[str, dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    selected_all: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        candidates = _rotation_candidates_for_hold_days(
            hold_days=hold_days,
            label=label,
            window=window,
            result=core_results[label],
            prices=prices,
        )
        spy_filtered, spy_blocked = spy_gate._apply_locked_spy_floor(candidates)
        selected, selection_skipped = parent.base._select_trades(spy_filtered)
        event_curve = parent.base._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        after_metrics[label] = parent.base._combined_metrics(
            core_results[label], event_curve, selected
        )
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
            "selected_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in selected), 2
            ),
            "selected_win_rate": round(
                sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0)
                / len(selected),
                4,
            )
            if selected
            else None,
            "surface_summary": parent.base._surface_summary(selected),
            "skipped_reason_counts": dict(skipped_reason_counts),
            "selected_trades": _selected_trade_rows(selected),
        }

    return {
        "hold_days": hold_days,
        "metrics": after_metrics,
        "surface_sleeve": surface_sleeve,
        "selected_trade_count": len(selected_all),
        "single_ticker_positive_share": _single_ticker_positive_share(selected_all),
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
        f"# {EXPERIMENT_ID} State-Surface Rotation Hold Days",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `hold_days` for the default-off rotation-only state-surface paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Hold days | Gate 4 | dEV | dPnL | EV Improved | EV Regressed | Trades | Max DD Worse | Single Ticker Positive Share |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        share = row["single_ticker_positive_share"]
        lines.append(
            "| {hold} | {passed} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {trades} | {dd:+.4%} | {share} |".format(
                hold=row["hold_days"],
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
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before DD | After DD | Sleeve trades |",
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
    for label, window in WINDOWS.items():
        result = parent._load_core_result(window)
        core_results[label] = result
        core_metrics[label] = parent.base._core_metrics(result)

    variants = [
        _variant_payload(
            hold_days=hold_days,
            core_results=core_results,
            prices=prices,
        )
        for hold_days in HOLD_DAY_VARIANTS
    ]
    baseline = next(row for row in variants if row["hold_days"] == BASELINE_HOLD_DAYS)
    baseline_metrics = baseline["metrics"]

    sweep_summary = []
    for variant in variants:
        gate4 = _gate4_for_variant(
            baseline_metrics=baseline_metrics,
            variant=variant,
        )
        sweep_summary.append(
            {
                "hold_days": variant["hold_days"],
                "is_identity_control": variant["hold_days"] == BASELINE_HOLD_DAYS,
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
    best_variant = next(row for row in variants if row["hold_days"] == best_summary["hold_days"])
    delta = best_summary["gate4"]["delta_metrics"]

    if best_summary["gate4"]["passed"]:
        decision = "accepted_shared_default_off_policy_hold_days"
        status = "accepted"
        interpretation = (
            "Changing the fixed hold horizon improved the accepted top-five "
            "rotation state-surface paper sleeve. The passing hold_days value "
            "should be promoted to the shared default-off state_surface_sleeve.py "
            "policy with parity coverage; live/default orders remain disabled."
        )
    else:
        decision = "rejected_state_surface_hold_days"
        status = "rejected"
        interpretation = (
            "No tested fixed hold horizon improved the accepted top-five "
            "rotation state-surface paper sleeve across the three fixed windows."
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_rotation_hold_days",
        "changed_variable": "hold_days",
        "change_summary": (
            "Sweep the fixed paper holding horizon for accepted top-five "
            "rotation-only state-surface paper candidates."
        ),
        "component": "quant/experiments",
        "mechanism_family": "state_aware_candidate_pool_lifecycle",
        "hypothesis": (
            "The accepted top-five rotation-only state-surface paper sleeve may "
            "be holding too briefly or too long. A fixed production-executable "
            "hold horizon can improve replacement value without adding tickers, "
            "changing scoring, retuning feature gates, or touching live orders."
        ),
        "alpha_hypothesis": {
            "category": "exit",
            "entry_exit_ranking_or_allocation": "default-off paper lifecycle",
            "playbook_alignment": (
                "Targets event-rotation replacement-value maturation after the "
                "accepted top-five queue. It avoids LLM soft-ranking data limits "
                "and does not broaden core live eligibility."
            ),
        },
        "history_check": {
            "exp-20260508-015": (
                "Rejected event-overlay hold-days sweep; that was the external "
                "event overlay, not the accepted top-five state-surface paper queue."
            ),
            "exp-20260517-014": "Accepted rotation-only state-surface paper eligibility.",
            "exp-20260517-016": "Accepted candidate-level SPY-relative 20d excess floor.",
            "exp-20260517-025": "Accepted top-five daily rotation paper candidate count.",
            "anti_repeat_boundary": (
                "This is not a ret20/ret5/ret60/volume/near-high threshold retry, "
                "not an active-position capacity retry, and not a candidate-count retry."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "exit alpha: vary fixed paper hold_days for the accepted top-five "
                "rotation state-surface queue"
            ),
            "2_history_check": (
                "Prior hold-days work was on the broad event overlay; current "
                "state-surface top-five queue has not had a current-stack hold "
                "horizon sweep after exp-20260517-025."
            ),
            "3_single_causal_variable": "hold_days",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; best non-control horizon "
                "must improve aggregate EV/PnL versus current accepted 20-day hold, "
                "improve at least two windows, regress zero windows, keep selected "
                f"trades >= {MIN_SELECTED_TRADES}, max drawdown drift <= "
                f"{MAX_DRAWDOWN_WORSE:.1%}, and single-ticker positive share <= "
                f"{MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_001_state_surface_rotation_hold_days.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "hold_days",
            "baseline_hold_days": BASELINE_HOLD_DAYS,
            "hold_day_variants": HOLD_DAY_VARIANTS,
            "best_hold_days": best_summary["hold_days"],
            "daily_candidate_count_locked": ACCEPTED_DAILY_CANDIDATE_COUNT,
            "locked_ret20_excess_spy_min": 0.0,
            "allowed_surfaces_locked": [TARGET_SURFACE],
            "decision_timing": "score after decision-date close; enter next trading day open",
            "candidate_source": "production universe only, excluding SPY/QQQ/IWM and existing same-day core candidates",
            "max_active_surface_positions": parent.base.MAX_ACTIVE_SURFACE_POSITIONS,
            "event_notional_usd": parent.base.EVENT_NOTIONAL,
            "locked_variables": [
                "core universe files",
                "signal generation",
                "entry filters",
                "candidate scoring weights",
                "daily candidate count",
                "risk sizing",
                "core position slots",
                "state-surface active capacity",
                "state-surface paper notional",
                "state-surface ret20_excess_spy gate",
                "gap cancels",
                "add-ons",
                "core exits",
                "LLM/news replay",
                "event bundle definitions",
                "event bundle notional/scalars",
                "production orders",
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
            "current_state_surface_top5_hold20_baseline_metrics": baseline_metrics,
            "baseline_hold_days": BASELINE_HOLD_DAYS,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "state_surface surface",
                "state_surface score",
                "state_surface rank",
                "state_surface decision_date",
                "state_surface features.ret20_excess_spy",
                "OHLCV next-session open",
                "OHLCV fixed-horizon exit close",
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
            "shared_policy_changed": best_summary["gate4"]["passed"],
            "backtester_adapter_changed": False,
            "run_adapter_changed": best_summary["gate4"]["passed"],
            "replay_only": False,
            "parity_test_added": best_summary["gate4"]["passed"],
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "shared_policy_file": "quant/state_surface_sleeve.py",
            "parity_test_file": "quant/test_state_surface_sleeve.py",
            "production_impact": (
                "Shared default-off paper policy would change only the state-surface "
                "paper holding horizon. The same state_surface_sleeve.py path is "
                "used by production and tests; live/default orders remain disabled."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft-ranking data remains sparse/PIT-limited; this deterministic "
                "state-surface lifecycle test uses replayable OHLCV fields."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if best_summary["gate4"]["passed"] else interpretation,
        "next_evidence_needed": (
            "Promote the accepted hold_days value in shared state_surface_sleeve.py, "
            "add parity coverage, and continue forward closed replacement-value observation."
            if best_summary["gate4"]["passed"]
            else "Keep the accepted 20-day state-surface paper hold; next state-surface alpha should use a different production-visible discriminator or forward replacement-value evidence."
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
            "docs/current_state.md",
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rotation hold days",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
            "best_hold_days": payload["parameters"]["best_hold_days"],
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
                    "best_hold_days": payload["parameters"]["best_hold_days"],
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
