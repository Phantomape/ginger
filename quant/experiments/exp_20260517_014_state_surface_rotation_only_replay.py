"""exp-20260517-014: state-surface rotation-only satellite replay.

Alpha search. Tests one candidate-pool variable on the current accepted stack:
only `rotation_breakout_leadership` state-surface rows are eligible for the
default-off state-surface satellite sleeve. Core A/B signals, ranking, sizing,
exits, event bundle notional/scalars, LLM/news behavior, and production orders
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


EXPERIMENT_ID = "exp-20260517-014"
EXPERIMENT_SLUG = "state_surface_rotation_only_replay"
TARGET_SURFACE = "rotation_breakout_leadership"
MIN_SELECTED_TRADES = 9
MAX_SINGLE_TICKER_POSITIVE_SHARE = 0.50

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiments import exp_20260507_016_state_surface_satellite_replay as base  # noqa: E402


WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

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


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_price_map() -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for window in WINDOWS.values():
        payload = _json_load(REPO_ROOT / window["snapshot"])
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict) or not row.get("Date"):
                    continue
                date_key = str(row["Date"])[:10]
                by_ticker_date[ticker_key][date_key] = {
                    "date": date_key,
                    "open": _float_or_none(row.get("Open")),
                    "close": _float_or_none(row.get("Close")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _audit_open_positions() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for section in ("positions", "observations"):
        rows.extend([row for row in payload.get(section, []) if isinstance(row, dict)])
    missing = []
    for row in rows:
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(path),
        "checked_rows": len(rows),
        "required_fields": ["entry_date", "target_price"],
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _load_core_result(window: dict[str, str]) -> dict[str, Any]:
    result = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    ).run()
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    return result


def _rotation_candidates(
    *,
    label: str,
    window: dict[str, str],
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    raw = base._raw_candidates(
        label=label,
        window=window,
        result=result,
        prices=prices,
    )
    return [
        row
        for row in raw
        if str(row.get("surface") or "") == TARGET_SURFACE
    ]


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict((label, base._delta(before[label], after[label])) for label in WINDOWS)
    baseline_ev = sum(float(before[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    after_ev = sum(float(after[label]["expected_value_score"] or 0.0) for label in WINDOWS)
    baseline_pnl = sum(float(before[label]["total_pnl"] or 0.0) for label in WINDOWS)
    after_pnl = sum(float(after[label]["total_pnl"] or 0.0) for label in WINDOWS)
    drawdown_delta = {
        label: round(
            float(after[label].get("max_drawdown_pct") or 0.0)
            - float(before[label].get("max_drawdown_pct") or 0.0),
            6,
        )
        for label in WINDOWS
    }
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 6),
        "after_ev_sum": round(after_ev, 6),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 6),
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
            if (after[label].get("expected_value_score") or 0)
            > (before[label].get("expected_value_score") or 0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("expected_value_score") or 0)
            < (before[label].get("expected_value_score") or 0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0)
            > (before[label].get("total_pnl") or 0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in WINDOWS
            if (after[label].get("total_pnl") or 0)
            < (before[label].get("total_pnl") or 0)
        ),
        "by_window_max_drawdown_delta": drawdown_delta,
        "max_drawdown_worse_max": max(drawdown_delta.values()) if drawdown_delta else 0.0,
    }


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    positive = [trade for trade in trades if float(trade.get("pnl") or 0.0) > 0]
    total_positive = sum(float(trade.get("pnl") or 0.0) for trade in positive)
    if total_positive <= 0:
        return None
    by_ticker: dict[str, float] = defaultdict(float)
    for trade in positive:
        by_ticker[str(trade.get("ticker") or "").upper()] += float(trade.get("pnl") or 0.0)
    return round(max(by_ticker.values()) / total_positive, 6) if by_ticker else None


def _artifact_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Sleeve trades | Sleeve PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {trades} | ${epnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                ddd=payload["delta_metrics"]["by_window_max_drawdown_delta"][label],
                trades=sleeve["selected_trade_count"],
                epnl=sleeve["selected_pnl"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} State-Surface Rotation-Only Replay",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single causal variable: state-surface satellite candidate eligibility is restricted to `rotation_breakout_leadership`. Core strategy logic, event bundle notional/scalars, exits, ranking, sizing, LLM/news, and production orders are unchanged.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Promoted only to shared default-off paper policy in `state_surface_sleeve.py`: candidate eligibility is `rotation_breakout_leadership` only, full `scored_candidates` audit remains available, and live/default orders remain disabled.",
            "",
        ]
    )


def build_payload() -> dict[str, Any]:
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prices = _load_price_map()
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    per_window: dict[str, dict[str, Any]] = OrderedDict()
    surface_contribution: dict[str, Any] = OrderedDict()
    all_selected: list[dict[str, Any]] = []

    for label, window in WINDOWS.items():
        result = _load_core_result(window)
        candidates = _rotation_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
        selected, skipped = base._select_trades(candidates)
        event_curve = base._event_equity_curve(
            selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = base._core_metrics(result)
        after_metrics[label] = base._combined_metrics(result, event_curve, selected)
        surface_summary = base._surface_summary(selected)
        surface_contribution[label] = surface_summary
        all_selected.extend(selected)
        per_window[label] = {
            "raw_rotation_candidate_count": len(candidates),
            "price_ready_rotation_candidate_count": sum(
                1 for row in candidates if row.get("status") == "price_ready"
            ),
            "selected_trade_count": len(selected),
            "selected_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in selected), 2),
            "selected_win_rate": round(
                sum(1 for trade in selected if float(trade.get("pnl") or 0.0) > 0) / len(selected),
                4,
            )
            if selected
            else None,
            "surface_summary": surface_summary,
            "skipped_reason_counts": dict(Counter(str(row.get("reason") or "unknown") for row in skipped)),
            "selected_trades": [
                {
                    "ticker": trade.get("ticker"),
                    "surface": trade.get("surface"),
                    "decision_date": trade.get("decision_date"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "rank": trade.get("rank"),
                    "score": trade.get("score"),
                    "pnl": trade.get("pnl"),
                    "net_return_pct": trade.get("net_return_pct"),
                }
                for trade in selected
            ],
        }

    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4_by_window = OrderedDict(
        (label, base._gate4(before_metrics[label], after_metrics[label])) for label in WINDOWS
    )
    selected_trade_count = len(all_selected)
    positive_share = _single_ticker_positive_share(all_selected)
    sample_guard_passed = selected_trade_count >= MIN_SELECTED_TRADES
    concentration_guard_passed = (
        positive_share is None or positive_share <= MAX_SINGLE_TICKER_POSITIVE_SHARE
    )
    passed_without_regression = (
        delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and sample_guard_passed
        and concentration_guard_passed
    )
    decision = (
        "accepted_for_shared_default_off_policy_review"
        if passed_without_regression
        else "rejected_state_surface_rotation_only"
    )
    interpretation = (
        "Rotation-only state-surface satellite passed the three-window replay gate; next step is shared default-off paper policy implementation and rerun before retaining any production-visible change."
        if passed_without_regression
        else "Rotation-only state-surface satellite did not clear the three-window gate; keep the current state-surface paper policy unchanged."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "state_surface_candidate_pool_surface_eligibility",
        "mechanism_family": "state_aware_candidate_pool_extension",
        "hypothesis": (
            "The current strongest repeated event/state alpha is rotation leadership. "
            "Restricting the state-surface satellite candidate pool to "
            "`rotation_breakout_leadership` may preserve the high-replacement-value "
            "surface while avoiding generic balanced/broad candidates that have been "
            "noisier in recent logs."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension",
            "entry_exit_ranking_or_allocation": "satellite entry/allocation",
            "playbook_alignment": (
                "Follows the event-rotation replacement-value lane, uses one "
                "production-visible replayable field, avoids LLM/SEC data limits, "
                "and does not sweep nearby notional scalars."
            ),
        },
        "historical_experiment_check": {
            "exp-20260509-010": (
                "Full state-surface satellite improved all canonical windows on the "
                "current-stack revalidation but remained replay-only."
            ),
            "exp-20260507-017": (
                "Broad+rotation surface prune was rejected because it regressed the "
                "late window. This run is narrower: rotation-only eligibility."
            ),
            "exp-20260517-010": (
                "Event-bundle rotation surface tilt is the strongest current "
                "replay-only event alpha; this tests the same surface as candidate "
                "eligibility instead of another notional scalar."
            ),
            "why_not_llm_or_sec": (
                "LLM soft-ranking and SEC semantic branches remain attribution- or "
                "sample-limited, so this run uses deterministic OHLCV state fields."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate-pool alpha: rotation_breakout_leadership surface-only "
                "state-surface satellite sleeve"
            ),
            "2_history_check": (
                "Nearby full surface passed replay-only; broad+rotation prune failed "
                "late; event rotation surface repeatedly leads. No current-stack "
                "rotation-only surface eligibility test found."
            ),
            "3_single_causal_variable": "state_surface_satellite_allowed_surface = rotation_breakout_leadership only",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, zero EV-regressed windows, "
                f"selected trades >= {MIN_SELECTED_TRADES}, and single-ticker "
                f"positive share <= {MAX_SINGLE_TICKER_POSITIVE_SHARE:.0%}."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260517_014_state_surface_rotation_only_replay.py"
            ),
        },
        "parameters": {
            "single_causal_variable": "state_surface_satellite_allowed_surface",
            "allowed_surfaces": [TARGET_SURFACE],
            "excluded_surfaces": [
                "balanced_state_leadership",
                "broad_breadth_trend_persistence",
                "mid_dispersion_selective_leadership",
            ],
            "decision_timing": "score after decision-date close; enter next trading day open",
            "candidate_source": "production universe only, excluding SPY/QQQ/IWM and existing same-day core candidates",
            "daily_candidate_count_source": base.DAILY_CANDIDATE_COUNT,
            "max_active_surface_positions": base.MAX_ACTIVE_SURFACE_POSITIONS,
            "hold_days": base.HOLD_DAYS,
            "event_notional_usd": base.EVENT_NOTIONAL,
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
            "baseline_metrics": before_metrics,
            "baseline_aggregate": {
                "expected_value_score_sum": delta["baseline_ev_sum"],
                "total_pnl_sum": delta["baseline_pnl_sum"],
            },
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "state_surface surface",
                "state_surface score",
                "state_surface decision_date",
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
                float(row.get("survival_rate") or 0.0) for row in after_metrics.values()
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in after_metrics.values()) >= 0.05,
        },
        "gate4": {
            "passed": passed_without_regression,
            "by_window": gate4_by_window,
            "aggregate_ev_delta": delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
            "windows_ev_improved": delta["windows_ev_improved"],
            "windows_ev_regressed": delta["windows_ev_regressed"],
            "selected_trade_count": selected_trade_count,
            "minimum_selected_trades": MIN_SELECTED_TRADES,
            "sample_guard_passed": sample_guard_passed,
            "single_ticker_positive_share": positive_share,
            "max_single_ticker_positive_share": MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "concentration_guard_passed": concentration_guard_passed,
            "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "surface_sleeve": per_window,
        "surface_contribution": surface_contribution,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"] for label in WINDOWS
        },
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        },
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "shared_policy_file": "quant/state_surface_sleeve.py",
            "parity_test_file": "quant/test_state_surface_sleeve.py",
            "production_impact": (
                "Default-off paper state-surface candidates are restricted to "
                "rotation_breakout_leadership; scored_candidates remain full-audit "
                "and live/default orders remain disabled."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm": (
                "LLM soft-ranking data remains sparse/PIT-limited; this run uses "
                "deterministic state-surface fields instead."
            ),
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed_without_regression else interpretation,
        "next_evidence_needed": (
            "Shared default-off paper policy promotion plus parity rerun."
            if passed_without_regression
            else "Do not promote rotation-only state-surface eligibility without a new field or fresh forward evidence."
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
        ],
    }


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface rotation-only replay",
            "status": payload["status"],
            "decision": payload["decision"],
            "changed_variable": payload["parameters"]["single_causal_variable"],
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
