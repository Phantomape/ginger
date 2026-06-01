"""exp-20260601-023: baseline earnings-DTE drift attribution.

Lane: measurement_repair.

Audit whether the current canonical baseline drift is explained by the
2026-05-31 change that made backtests prefer daily PIT earnings snapshots for
`days_to_earnings`. This runner changes no shared strategy code.

No JavaScript was used.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260601-023"
STEM = "exp_20260601_023_baseline_earnings_dte_drift_attribution"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
JSONL = ROOT / "docs" / "experiment_log.jsonl"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

DOCS_ACCEPTED_BASELINE = {
    "late_strong": {
        "expected_value_score": 5.1628,
        "total_pnl": 117_072.92,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
        "max_drawdown_pct": 0.0665,
    },
    "mid_weak": {
        "expected_value_score": 2.1402,
        "total_pnl": 78_110.11,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
        "max_drawdown_pct": 0.1119,
    },
    "old_thin": {
        "expected_value_score": 0.5911,
        "total_pnl": 39_667.96,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
        "max_drawdown_pct": 0.1001,
    },
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "parity_test_added": False,
    "replay_only": False,
    "trade_enabled": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "production_watchlist_changed": False,
    "alters_orders": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_output(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return (proc.stdout or proc.stderr or "").strip()


def _old_calendar_dte_earnings_dict_for(self, today, calendar_dates, ticker=None):
    """Compatibility copy of the pre-bb4ced9e9 DTE source semantics."""
    import numpy as np

    today_date = today.date() if hasattr(today, "date") else today
    future = [d for d in calendar_dates if d > today_date]
    base = {
        "next_earnings_date": None,
        "days_to_earnings": None,
        "eps_estimate": None,
        "eps_actual_last": None,
        "historical_surprise_pct": [],
        "avg_historical_surprise_pct": None,
    }
    if not future:
        return base

    nxt = future[0]
    try:
        dte = int(np.busday_count(today_date, nxt))
    except Exception:
        dte = None
    base["next_earnings_date"] = str(nxt)
    base["days_to_earnings"] = dte

    if ticker and self._earnings_snapshots:
        today_str = (
            today_date.strftime("%Y%m%d")
            if hasattr(today_date, "strftime")
            else str(today_date).replace("-", "")
        )
        candidates = [d for d in self._earnings_snapshots if d <= today_str]
        if candidates:
            snap_date = max(candidates)
            snap = self._earnings_snapshots[snap_date].get(ticker, {})
            if snap.get("eps_estimate") is not None:
                base["eps_estimate"] = snap["eps_estimate"]
            if snap.get("eps_actual_last") is not None:
                base["eps_actual_last"] = snap["eps_actual_last"]
            hist = snap.get("historical_surprise_pct")
            if isinstance(hist, list):
                base["historical_surprise_pct"] = hist
            if snap.get("avg_historical_surprise_pct") is not None:
                base["avg_historical_surprise_pct"] = snap[
                    "avg_historical_surprise_pct"
                ]
            elif base["historical_surprise_pct"]:
                vals = [
                    float(x)
                    for x in base["historical_surprise_pct"]
                    if isinstance(x, (int, float))
                ]
                if vals:
                    base["avg_historical_surprise_pct"] = sum(vals) / len(vals)

    return base


def _metric_row(result: dict[str, Any]) -> dict[str, Any]:
    result["expected_value_score"] = compute_expected_value_score(result)
    return {
        "expected_value_score": round(float(result.get("expected_value_score") or 0.0), 4),
        "total_pnl": round(float(result.get("total_pnl") or 0.0), 2),
        "strategy_total_return_pct": round(
            float((result.get("benchmarks") or {}).get("strategy_total_return_pct") or 0.0),
            4,
        ),
        "sharpe_daily": round(float(result.get("sharpe_daily") or 0.0), 4),
        "max_drawdown_pct": round(float(result.get("max_drawdown_pct") or 0.0), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": round(float(result.get("survival_rate") or 0.0), 4),
    }


def _run_baseline(*, calendar_dte_compat: bool) -> dict[str, dict[str, Any]]:
    universe = get_universe()
    config = {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True}
    rows: dict[str, dict[str, Any]] = {}
    original = BacktestEngine._earnings_dict_for
    if calendar_dte_compat:
        BacktestEngine._earnings_dict_for = _old_calendar_dte_earnings_dict_for
    try:
        for label, spec in WINDOWS.items():
            engine = BacktestEngine(
                universe=universe,
                start=spec["start"],
                end=spec["end"],
                config=config,
                replay_llm=False,
                replay_news=False,
                ohlcv_snapshot_path=spec["snapshot"],
                include_oracle_diagnostics=False,
            )
            result = engine.run()
            if "error" in result:
                rows[label] = {"error": result["error"]}
            else:
                rows[label] = _metric_row(result)
    finally:
        BacktestEngine._earnings_dict_for = original
    return rows


def _compare_variant(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    for label, docs in DOCS_ACCEPTED_BASELINE.items():
        actual = rows.get(label) or {}
        ev_delta = round(
            float(actual.get("expected_value_score") or 0.0)
            - float(docs["expected_value_score"]),
            6,
        )
        pnl_delta = round(float(actual.get("total_pnl") or 0.0) - float(docs["total_pnl"]), 2)
        trade_delta = int(actual.get("trade_count") or 0) - int(docs["trade_count"])
        signal_delta = int(actual.get("signals_generated") or 0) - int(
            docs["signals_generated"]
        )
        survived_delta = int(actual.get("signals_survived") or 0) - int(
            docs["signals_survived"]
        )
        by_window[label] = {
            "docs": docs,
            "actual": actual,
            "expected_value_score_delta": ev_delta,
            "total_pnl_delta": pnl_delta,
            "trade_count_delta": trade_delta,
            "signals_generated_delta": signal_delta,
            "signals_survived_delta": survived_delta,
            "matches_docs_baseline": (
                abs(ev_delta) <= 0.01
                and abs(pnl_delta) <= 100.0
                and trade_delta == 0
                and signal_delta == 0
                and survived_delta == 0
            ),
        }

    docs_ev = sum(row["expected_value_score"] for row in DOCS_ACCEPTED_BASELINE.values())
    docs_pnl = sum(row["total_pnl"] for row in DOCS_ACCEPTED_BASELINE.values())
    actual_ev = sum(
        float((rows.get(label) or {}).get("expected_value_score") or 0.0)
        for label in WINDOWS
    )
    actual_pnl = sum(
        float((rows.get(label) or {}).get("total_pnl") or 0.0) for label in WINDOWS
    )
    return {
        "by_window": by_window,
        "aggregate": {
            "docs_expected_value_score": round(docs_ev, 4),
            "actual_expected_value_score": round(actual_ev, 4),
            "expected_value_score_delta": round(actual_ev - docs_ev, 6),
            "docs_total_pnl": round(docs_pnl, 2),
            "actual_total_pnl": round(actual_pnl, 2),
            "total_pnl_delta": round(actual_pnl - docs_pnl, 2),
        },
        "matches_all_windows": all(row["matches_docs_baseline"] for row in by_window.values()),
    }


def _gap_reduction(current: dict[str, Any], compat: dict[str, Any]) -> dict[str, Any]:
    current_gap = abs(float(current["aggregate"]["expected_value_score_delta"]))
    compat_gap = abs(float(compat["aggregate"]["expected_value_score_delta"]))
    current_pnl_gap = abs(float(current["aggregate"]["total_pnl_delta"]))
    compat_pnl_gap = abs(float(compat["aggregate"]["total_pnl_delta"]))
    return {
        "ev_gap_reduction": round(current_gap - compat_gap, 6),
        "ev_gap_reduction_pct": (
            round((current_gap - compat_gap) / current_gap, 6) if current_gap else None
        ),
        "pnl_gap_reduction": round(current_pnl_gap - compat_pnl_gap, 2),
        "pnl_gap_reduction_pct": (
            round((current_pnl_gap - compat_pnl_gap) / current_pnl_gap, 6)
            if current_pnl_gap
            else None
        ),
    }


def _audit_open_positions() -> dict[str, Any]:
    path = ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"passed": False, "path": _repo_rel(path), "reason": "missing_file"}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {"passed": False, "path": _repo_rel(path), "reason": str(exc)}
    positions = data.get("positions") if isinstance(data, dict) else data
    if not isinstance(positions, list):
        return {"passed": False, "path": _repo_rel(path), "reason": "positions_not_list"}
    missing = []
    for idx, position in enumerate(positions):
        if not isinstance(position, dict):
            missing.append({"index": idx, "field": "position_not_dict"})
            continue
        for field in ("entry_date", "target_price"):
            if position.get(field) in (None, ""):
                missing.append(
                    {
                        "index": idx,
                        "ticker": position.get("ticker"),
                        "field": field,
                    }
                )
    return {
        "passed": not missing,
        "path": _repo_rel(path),
        "position_count": len(positions),
        "missing_required_fields": missing,
    }


def _write_card(payload: dict[str, Any]) -> None:
    current = payload["comparisons"]["current_pit_snapshot_dte"]["aggregate"]
    compat = payload["comparisons"]["calendar_dte_compat"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} baseline earnings-DTE drift attribution",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Current aggregate EV/PnL: `{current['actual_expected_value_score']:.4f}` / `${current['actual_total_pnl']:,.2f}`",
        f"- Docs aggregate EV/PnL: `{current['docs_expected_value_score']:.4f}` / `${current['docs_total_pnl']:,.2f}`",
        f"- Calendar-DTE compatibility aggregate EV/PnL: `{compat['actual_expected_value_score']:.4f}` / `${compat['actual_total_pnl']:,.2f}`",
        f"- EV gap reduction from compatibility replay: `{payload['drift_attribution']['ev_gap_reduction_pct']}`",
        "",
        "## Window Comparison",
        "",
        "| window | docs EV | current EV | compat EV | current signals | compat signals | docs signals |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    current_rows = payload["comparisons"]["current_pit_snapshot_dte"]["by_window"]
    compat_rows = payload["comparisons"]["calendar_dte_compat"]["by_window"]
    for label in WINDOWS:
        docs = current_rows[label]["docs"]
        cur = current_rows[label]["actual"]
        com = compat_rows[label]["actual"]
        lines.append(
            f"| {label} | {docs['expected_value_score']:.4f} | "
            f"{cur.get('expected_value_score', 0):.4f} | "
            f"{com.get('expected_value_score', 0):.4f} | "
            f"{cur.get('signals_generated')} | {com.get('signals_generated')} | "
            f"{docs['signals_generated']} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["conclusion"],
            "",
            "This audit did not change entries, exits, ranking, sizing, LLM/news, watchlists, or orders.",
            "",
        ]
    )
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_jsonl(payload: dict[str, Any]) -> None:
    JSONL.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": payload["timestamp"],
            "status": payload["status"],
            "lane": payload["lane"],
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "changed_variable": payload["changed_variable"],
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260601-016",
                "exp-20260601-021",
                "exp-20260601-022",
                "bb4ced9e9",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "baseline_drift_source_attribution",
            "before_metrics": payload["comparisons"]["current_pit_snapshot_dte"][
                "aggregate"
            ],
            "after_metrics": payload["comparisons"]["calendar_dte_compat"][
                "aggregate"
            ],
            "delta_metrics": payload["drift_attribution"],
            "production_impact": PRODUCTION_IMPACT,
            "decision": payload["decision"],
            "rejection_reason": None
            if payload["status"].startswith("accepted")
            else payload["decision"],
            "next_retry_requires": payload["next_retry_requires"],
            "related_files": payload["related_files"],
            "anti_js": "No JavaScript was used.",
        },
        sort_keys=True,
    )
    existing = JSONL.read_text(encoding="utf-8") if JSONL.exists() else ""
    if f'"experiment_id": "{EXPERIMENT_ID}"' not in existing:
        with JSONL.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(line + "\n")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket: dict[str, Any] = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "result": payload["drift_attribution"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def run() -> dict[str, Any]:
    timestamp = _utc_now()
    current_rows = _run_baseline(calendar_dte_compat=False)
    compat_rows = _run_baseline(calendar_dte_compat=True)
    current_cmp = _compare_variant(current_rows)
    compat_cmp = _compare_variant(compat_rows)
    attribution = _gap_reduction(current_cmp, compat_cmp)
    open_positions = _audit_open_positions()

    if compat_cmp["matches_all_windows"]:
        status = "accepted_measurement_repair_drift_source_identified"
        decision = "accepted_calendar_dte_compat_restores_docs_baseline"
        conclusion = (
            "The baseline drift is explained by the PIT earnings snapshot DTE "
            "replay change: restoring calendar-only DTE semantics reproduces "
            "the documented accepted baseline across all three windows. The "
            "correct next step is a deliberate parity decision: either update "
            "the canonical baseline to the more production-faithful PIT "
            "snapshot DTE replay, or explicitly version the old baseline."
        )
    elif (attribution["ev_gap_reduction_pct"] or 0.0) >= 0.5:
        status = "observed_only_partial_drift_source_identified"
        decision = "partial_calendar_dte_compat_reduces_baseline_drift"
        conclusion = (
            "Calendar-only DTE compatibility materially reduces the baseline "
            "gap but does not fully restore the documented baseline. PIT "
            "earnings snapshot DTE replay is a major source, but another drift "
            "source remains before alpha can be retained."
        )
    else:
        status = "rejected_earnings_dte_not_primary_drift_source"
        decision = "calendar_dte_compat_does_not_explain_baseline_drift"
        conclusion = (
            "Calendar-only DTE compatibility does not materially restore the "
            "documented accepted baseline. The current blocker remains open "
            "and should be traced elsewhere before retaining positive alpha."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "measurement_repair",
        "hypothesis": (
            "Audit whether PIT earnings snapshot days-to-earnings replay "
            "explains the current canonical baseline drift blocking alpha "
            "retention."
        ),
        "change_type": "baseline_attribution_repair",
        "mechanism_family": "baseline_attribution_repair",
        "trial_family": "baseline_earnings_dte_drift_attribution",
        "trial_variant_id": "calendar_dte_compatibility_replay",
        "changed_variable": "earnings_snapshot_dte_replay_semantics",
        "single_causal_variable": "current PIT snapshot DTE versus calendar-only DTE compatibility replay",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "current_variant": "normal current BacktestEngine",
            "compat_variant": "pre-bb4ced9e9 calendar-only days_to_earnings semantics",
            "replay_llm": False,
            "replay_news": False,
            "regime_aware_exit": True,
            "replay_partial_reduces": True,
            "oracle_diagnostics": False,
        },
        "comparisons": {
            "current_pit_snapshot_dte": current_cmp,
            "calendar_dte_compat": compat_cmp,
        },
        "drift_attribution": attribution,
        "gate2": {
            "open_positions": open_positions,
            "passed": open_positions["passed"],
        },
        "gate3": {
            "passed": min(
                float((row.get("actual") or {}).get("survival_rate") or 0.0)
                for row in current_cmp["by_window"].values()
            )
            >= 0.05,
            "new_filter_added": False,
        },
        "production_impact": PRODUCTION_IMPACT,
        "conclusion": conclusion,
        "next_retry_requires": [
            "Resolve the canonical baseline version before retaining gross-margin or consensus alpha leads.",
            "If PIT snapshot DTE is accepted as more production-faithful, update docs/backtesting.md and docs/current_state.md with the new three-window baseline.",
            "If the old baseline remains canonical, isolate the snapshot DTE replay behind an explicit versioned backtest protocol.",
            "Rerun exp-20260601-021 gross-margin evidence only after the baseline decision is recorded.",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            "quant/backtester.py",
            "data/experiments/exp-20260601-016/exp_20260601_016_current_baseline_parity_audit.json",
            "data/experiments/exp-20260601-021/exp_20260601_021_companyfacts_gross_margin_rs_candidate_pool.json",
        ],
        "git": {
            "head": _git_output(["rev-parse", "--short", "HEAD"]),
            "dirty_status_count": len(_git_output(["status", "--short"]).splitlines()),
        },
        "anti_js": "No JavaScript was used.",
    }
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_card(payload)
    _update_ticket(payload)
    _append_jsonl(payload)
    return payload


def main() -> None:
    payload = run()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "drift_attribution": payload["drift_attribution"],
                "current_aggregate": payload["comparisons"][
                    "current_pit_snapshot_dte"
                ]["aggregate"],
                "compat_aggregate": payload["comparisons"]["calendar_dte_compat"][
                    "aggregate"
                ],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
