"""exp-20260511-113: SEC financial-report pending quality ranking.

Alpha search on one causal variable: the default-off SEC financial-report
paper sleeve's pending-fill priority. The accepted exp-20260511-112 sleeve
capacity is fixed at three paper positions; this replay compares the current
age-first pending queue against a quality-first queue that fills the strongest
known T+1 excess reaction first when capacity is scarce.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EXPERIMENT_ID = "exp-20260511-113"
STEM = "exp_20260511_113_sec_financial_report_pending_quality_rank"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import sec_financial_report_event_sleeve as sleeve_module  # noqa: E402
from exp_20260511_112_sec_financial_report_t1_sleeve_capacity import (  # noqa: E402
    SOURCE_EXP100_JSON,
    STARTING_CAPITAL,
    WINDOWS,
    _aggregate,
    _combine_curves,
    _core_metrics,
    _delta,
    _equity_metrics,
    _load_exp100,
    _load_snapshot_prices,
    _normalise_core_curve,
    _rebuild_sleeve_state,
    _round,
    _rows_by_t1_date,
    _run_core_backtest,
    _safe,
    _write_json,
)
from sec_financial_report_event_sleeve import (  # noqa: E402
    DEFAULT_MAX_POSITIONS,
    SLEEVE_NAME,
    build_sec_financial_report_event_sleeve_snapshot,
    empty_sec_financial_report_event_sleeve_state,
)


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = (
    REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
DOC_ARTIFACT = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_sec_financial_report_pending_quality_rank.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_VARIANT = "age_first_t1_excess"
PROMOTION_VARIANT = "quality_first_t1_excess"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _float_or_zero(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _quality_first_pending_sort_key(entry: dict[str, Any]) -> tuple[float, str, str]:
    candidate = entry.get("candidate") or {}
    return (
        -_float_or_zero(candidate.get("t1_excess_return_vs_spy")),
        str(entry.get("created_asof") or ""),
        str(entry.get("ticker") or ""),
    )


def _patch_pending_sort(
    sort_key: Callable[[dict[str, Any]], tuple[Any, ...]] | None,
) -> Callable[[dict[str, Any]], tuple[Any, ...]]:
    original = sleeve_module._pending_sort_key
    if sort_key is not None:
        sleeve_module._pending_sort_key = sort_key
    return original


def _restore_pending_sort(
    original: Callable[[dict[str, Any]], tuple[Any, ...]],
) -> None:
    sleeve_module._pending_sort_key = original


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


def _upsert_registry(payload: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8-sig"))
    else:
        registry = {"experiments": []}
    experiments = [
        row
        for row in registry.get("experiments", [])
        if row.get("experiment_id") != EXPERIMENT_ID
    ]
    experiments.append(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": payload["hypothesis"],
            "lane": "alpha_search",
            "owner": "alpha-search",
            "status": payload["status"],
            "ticket_file": f"experiments/tickets/{EXPERIMENT_ID}.json",
            "updated_at": payload["timestamp"],
        }
    )
    registry["experiments"] = sorted(
        experiments, key=lambda row: str(row.get("experiment_id") or "")
    )
    _write_json(EXPERIMENT_REGISTRY, registry)


def _run_sleeve_replay(
    window_label: str,
    window: dict[str, str],
    window_payload: dict[str, Any],
    *,
    pending_sort_key: Callable[[dict[str, Any]], tuple[Any, ...]] | None,
) -> dict[str, Any]:
    original_sort = _patch_pending_sort(pending_sort_key)
    try:
        prices_by_date = _load_snapshot_prices(window["snapshot"])
        candidates_by_t1 = _rows_by_t1_date(window_payload)
        state = empty_sec_financial_report_event_sleeve_state()
        skipped_entries: list[dict[str, Any]] = []
        pnl_by_date: OrderedDict[str, float] = OrderedDict()
        max_open_positions = 0
        max_gross_notional = 0.0
        enqueued_candidates = 0

        for as_of, prices in prices_by_date.items():
            candidates = candidates_by_t1.get(as_of, [])
            enqueued_candidates += len(candidates)
            queue = {
                "queue_name": "SEC_FINANCIAL_REPORT_T1_DRIFT_QUEUE_REPLAY",
                "rule_version": "exp-20260511-100-replay",
                "enabled": False,
                "asof_date": as_of,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "data_source": {
                    "status": "replay",
                    "source_experiment": "exp-20260511-100",
                    "window": window_label,
                },
            }
            snapshot = build_sec_financial_report_event_sleeve_snapshot(
                sec_financial_report_t1_queue=queue,
                as_of=as_of,
                open_prices=prices["open"],
                current_prices=prices["close"],
                state=state,
                config={"max_positions": DEFAULT_MAX_POSITIONS},
                persist=False,
            )
            skipped_entries.extend(snapshot.get("skipped_entries_today") or [])
            state = _rebuild_sleeve_state(snapshot, skipped_entries)
            realized = float(snapshot.get("realized_pnl_to_date") or 0.0)
            unrealized = float(snapshot.get("unrealized_pnl") or 0.0)
            pnl_by_date[as_of] = realized + unrealized
            open_positions = snapshot.get("open_positions") or []
            max_open_positions = max(max_open_positions, len(open_positions))
            max_gross_notional = max(
                max_gross_notional,
                sum(float(item.get("notional") or 0.0) for item in open_positions),
            )
    finally:
        _restore_pending_sort(original_sort)

    closed_positions = state.get("closed_positions") or []
    wins = sum(1 for item in closed_positions if float(item.get("pnl") or 0.0) > 0)
    sleeve_curve = [
        (date_value, STARTING_CAPITAL + pnl) for date_value, pnl in pnl_by_date.items()
    ]
    standalone_metrics = _equity_metrics(
        sleeve_curve,
        trade_count=len(closed_positions),
        win_rate=(wins / len(closed_positions) if closed_positions else None),
    )
    standalone_metrics.update(
        {
            "candidate_count": enqueued_candidates,
            "closed_trade_count": len(closed_positions),
            "open_position_count_end": len(state.get("open_positions") or []),
            "skipped_capacity_count": len(skipped_entries),
            "max_open_positions": max_open_positions,
            "max_gross_notional": _round(max_gross_notional, 2),
        }
    )
    return {
        "daily_pnl": list(pnl_by_date.items()),
        "metrics": standalone_metrics,
        "sample_closed_positions": closed_positions[:12],
        "closed_tickers": [
            str(item.get("ticker") or "").upper() for item in closed_positions
        ],
    }


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
    pending_sort_key: Callable[[dict[str, Any]], tuple[Any, ...]] | None,
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            pending_sort_key=pending_sort_key,
        )
        core_curve = core_results[label]["equity_curve"]
        combined_curve = _combine_curves(core_curve, sleeve["daily_pnl"])
        core_metrics = core_results[label]["metrics"]
        combined_metrics = _equity_metrics(
            combined_curve,
            trade_count=int(core_metrics.get("trade_count") or 0)
            + int(sleeve["metrics"].get("closed_trade_count") or 0),
            win_rate=None,
            signals_generated=core_metrics.get("signals_generated"),
            signals_survived=core_metrics.get("signals_survived"),
        )
        by_window[label] = {
            "combined_metrics": combined_metrics,
            "core_metrics": core_metrics,
            "sleeve_metrics": sleeve["metrics"],
            "closed_tickers": sleeve["closed_tickers"],
        }
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _window_checks(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for label in WINDOWS:
        after_m = after["by_window"][label]["combined_metrics"]
        before_m = before["by_window"][label]["combined_metrics"]
        out[label] = {
            "ev_delta": _round(
                float(after_m["expected_value_score"])
                - float(before_m["expected_value_score"]),
                6,
            ),
            "pnl_delta": _round(
                float(after_m["total_pnl"]) - float(before_m["total_pnl"]),
                2,
            ),
            "max_drawdown_delta": _round(
                float(after_m["max_drawdown_pct"])
                - float(before_m["max_drawdown_pct"]),
                6,
            ),
            "closed_trade_delta": int(
                after["by_window"][label]["sleeve_metrics"].get("closed_trade_count")
                or 0
            )
            - int(
                before["by_window"][label]["sleeve_metrics"].get("closed_trade_count")
                or 0
            ),
        }
    return out


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _delta(after["aggregate"], before["aggregate"])
    checks = _window_checks(after, before)
    ev_positive_windows = sum(1 for row in checks.values() if row["ev_delta"] > 0)
    ev_regressed_windows = sum(1 for row in checks.values() if row["ev_delta"] < 0)
    pnl_positive_windows = sum(1 for row in checks.values() if row["pnl_delta"] > 0)
    max_drawdown_delta_max = max(row["max_drawdown_delta"] for row in checks.values())
    passed = (
        (aggregate_delta.get("expected_value_score_sum_delta") or 0.0) > 0
        and (aggregate_delta.get("sleeve_total_pnl_sum_delta") or 0.0) >= 2_500.0
        and ev_positive_windows >= 2
        and ev_regressed_windows == 0
        and pnl_positive_windows >= 2
        and max_drawdown_delta_max <= 0.02
    )
    return {
        "aggregate_delta": aggregate_delta,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "passed": passed,
        "pnl_positive_windows": pnl_positive_windows,
        "rule": (
            "Pass if aggregate EV improves, sleeve PnL delta >= $2.5k, EV "
            "improves in at least two windows with zero EV-regression windows, "
            "PnL improves in at least two windows, and no window adds more than "
            "2 percentage points of drawdown."
        ),
        "window_checks": checks,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report pending quality ranking",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Changed variable: `{payload['changed_variable']}`",
        "- Baseline: pending entries fill by created date first, then T+1 excess.",
        "- Variant: pending entries fill by T+1 excess first, then created date.",
        "- Replay path: production `build_sec_financial_report_event_sleeve_snapshot`, persist disabled.",
        "",
        "## Aggregate",
        "",
        "| Variant | EV sum | Total PnL | Sleeve PnL | Sleeve closed | Max DD max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["variants"].items():
        agg = row["aggregate"]
        lines.append(
            f"| {name} | {agg['expected_value_score_sum']:.6f} | "
            f"${agg['total_pnl_sum']:,.2f} | ${agg['sleeve_total_pnl_sum']:,.2f} | "
            f"{agg['sleeve_closed_trade_count_sum']} | {agg['max_drawdown_pct_max']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            json.dumps(_safe(payload["gate"]), ensure_ascii=False, indent=2, sort_keys=True),
            "",
            "## Production impact",
            "",
            (
                "No live orders changed. If accepted, the change must be promoted "
                "only by changing the shared default-off paper sleeve pending sort "
                "helper and by adding a focused no-orders ranking test."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    now = _utc_now()
    exp100 = _load_exp100()

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants = OrderedDict(
        [
            (
                BASELINE_VARIANT,
                _run_variant(
                    core_results=core_results,
                    exp100=exp100,
                    pending_sort_key=None,
                ),
            ),
            (
                PROMOTION_VARIANT,
                _run_variant(
                    core_results=core_results,
                    exp100=exp100,
                    pending_sort_key=_quality_first_pending_sort_key,
                ),
            ),
        ]
    )
    before = variants[BASELINE_VARIANT]
    after = variants[PROMOTION_VARIANT]
    gate = _gate(after, before)
    decision = (
        "accepted_default_off_pending_quality_rank"
        if gate["passed"]
        else "rejected_pending_quality_rank"
    )

    payload: dict[str, Any] = {
        "after_metrics": after["by_window"],
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "before_metrics": before["by_window"],
        "change_type": "alpha_search_ranking",
        "changed_variable": "sec_financial_report_pending_fill_priority",
        "decision": decision,
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "experiment_id": EXPERIMENT_ID,
        "gate": gate,
        "hypothesis": (
            "Inside the accepted max-3 default-off SEC financial-report T+1 paper "
            "sleeve, scarce paper capacity should fill the strongest pending T+1 "
            "excess reaction before older lower-quality pending rows."
        ),
        "lane": "alpha_search",
        "llm_metrics": {"used_llm": False, "llm_role_changed": False},
        "parameters": {
            "baseline_pending_sort": "created_asof, -t1_excess_return_vs_spy, ticker",
            "candidate_pending_sort": "-t1_excess_return_vs_spy, created_asof, ticker",
            "max_positions": DEFAULT_MAX_POSITIONS,
            "source_candidate_artifact": str(SOURCE_EXP100_JSON.relative_to(REPO_ROOT)),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "alters_candidate_ranking": True,
            "default_off_paper_only": True,
            "live_orders_changed": False,
            "sleeve": SLEEVE_NAME,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "ranking/capital allocation: use quality-first pending fill "
                "priority for the SEC financial-report T+1 paper sleeve."
            ),
            "2_history_check": (
                "exp-20260511-112 tested capacity only; exp-20260510-027 and "
                "exp-20260511-007 tested cohort slices. No recorded experiment "
                "changed the pending-fill priority inside the production sleeve."
            ),
            "3_single_causal_variable": "pending queue fill priority only",
            "4_acceptance_standard": (
                "Three fixed windows, aggregate EV improvement, >=$2.5k sleeve "
                "PnL delta, no window EV regression, drawdown delta <=2pp."
            ),
            "5_reproducibility": (
                f"Run .venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py"
            ),
        },
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(DOC_LOG.relative_to(REPO_ROOT)),
            str(DOC_TICKET.relative_to(REPO_ROOT)),
            str(DOC_ARTIFACT.relative_to(REPO_ROOT)),
        ],
        "single_causal_variable": "sec_financial_report_pending_fill_priority",
        "status": "accepted_candidate" if gate["passed"] else "rejected",
        "timestamp": now,
        "variants": variants,
    }
    payload["rejection_reason"] = (
        None
        if gate["passed"]
        else "Quality-first pending fill did not clear the three-window ranking gate."
    )

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": "alpha_search",
        "owner": "alpha-search",
        "status": payload["status"],
        "created_at": now,
        "updated_at": now,
        "next_action": (
            "Promote through the shared paper sleeve helper plus focused no-orders test."
            if gate["passed"]
            else "Do not change SEC paper pending priority without forward evidence."
        ),
    }
    log_payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "date_range": {
            "primary": {
                "start": WINDOWS["late_strong"]["start"],
                "end": WINDOWS["late_strong"]["end"],
            },
            "secondary": [
                {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
                {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
            ],
        },
        "backtest_protocol": payload["backtest_protocol"],
        "parameters": payload["parameters"],
        "before_metrics": before["aggregate"],
        "after_metrics": after["aggregate"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": gate["aggregate_delta"].get(
            "expected_value_score_sum_delta"
        ),
        "decision": decision,
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": (
            "Shared helper promotion and forward default-off paper observation."
            if gate["passed"]
            else "Forward out-of-sample replacement-value evidence for quality-first pending fills."
        ),
        "production_impact": payload["production_impact"],
    }

    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, log_payload)
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, log_payload)
    _upsert_registry(payload)

    print(json.dumps(_safe(log_payload), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
