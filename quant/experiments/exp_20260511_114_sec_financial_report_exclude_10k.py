"""exp-20260511-114: SEC financial-report T+1 excludes 10-K rows.

Alpha search on one causal variable: the default-off SEC financial-report T+1
paper queue's form eligibility. The accepted exp-20260511-112 max-3 paper
capacity is fixed; this replay tests whether excluding 10-K periodic reports
improves replacement value while keeping earnings 8-K and 10-Q rows.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260511-114"
STEM = "exp_20260511_114_sec_financial_report_exclude_10k"
REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from exp_20260511_112_sec_financial_report_t1_sleeve_capacity import (  # noqa: E402
    SOURCE_EXP100_JSON,
    WINDOWS,
    _aggregate,
    _combine_curves,
    _core_metrics,
    _delta,
    _equity_metrics,
    _load_exp100,
    _normalise_core_curve,
    _round,
    _run_core_backtest,
    _run_sleeve_replay,
    _safe,
    _write_json,
)
from sec_financial_report_event_sleeve import DEFAULT_MAX_POSITIONS  # noqa: E402


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
    / f"{EXPERIMENT_ID}_sec_financial_report_exclude_10k.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_VARIANT = "include_10k"
PROMOTION_VARIANT = "exclude_10k"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


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


def _filtered_exp100(exp100: dict[str, Any]) -> dict[str, Any]:
    filtered = json.loads(json.dumps(exp100))
    for window in filtered.get("windows", {}).values():
        rows = window.get("candidate_rows") or []
        window["candidate_rows"] = [
            row for row in rows if str(row.get("form_base") or "").upper() != "10-K"
        ]
    return filtered


def _run_variant(
    *,
    core_results: dict[str, dict[str, Any]],
    exp100: dict[str, Any],
) -> dict[str, Any]:
    by_window = {}
    for label, window in WINDOWS.items():
        sleeve = _run_sleeve_replay(
            label,
            window,
            exp100["windows"][label],
            max_positions=DEFAULT_MAX_POSITIONS,
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
            "excluded_10k_candidate_count": 0,
        }
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _count_10k_by_window(exp100: dict[str, Any]) -> dict[str, int]:
    out = {}
    for label, window in exp100.get("windows", {}).items():
        out[label] = sum(
            1
            for row in window.get("candidate_rows") or []
            if str(row.get("form_base") or "").upper() == "10-K"
        )
    return out


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
            "sleeve_closed_trade_delta": int(
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
        and (aggregate_delta.get("sleeve_total_pnl_sum_delta") or 0.0) > 0
        and ev_positive_windows >= 2
        and ev_regressed_windows == 0
        and pnl_positive_windows >= 2
        and max_drawdown_delta_max <= 0.0
    )
    return {
        "aggregate_delta": aggregate_delta,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "max_drawdown_delta_max": _round(max_drawdown_delta_max, 6),
        "passed": passed,
        "pnl_positive_windows": pnl_positive_windows,
        "rule": (
            "Pass if aggregate EV and sleeve PnL improve, EV improves in at "
            "least two windows with zero EV-regression windows, PnL improves in "
            "at least two windows, and max drawdown does not worsen."
        ),
        "window_checks": checks,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} SEC financial-report exclude 10-K",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Changed variable: `{payload['changed_variable']}`",
        f"- Excluded 10-K rows by window: `{payload['excluded_10k_candidate_count']}`",
        "- Replay path: accepted max-3 default-off paper sleeve; no live orders.",
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
                "No live orders changed in this replay. If accepted, promote only "
                "through shared SEC queue qualification and focused default-off "
                "tests; keep the paper sleeve trade-disabled."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    now = _utc_now()
    exp100 = _load_exp100()
    filtered = _filtered_exp100(exp100)
    excluded_counts = _count_10k_by_window(exp100)

    core_results: dict[str, dict[str, Any]] = {}
    for label, window in WINDOWS.items():
        result = _run_core_backtest(window)
        core_results[label] = {
            "metrics": _core_metrics(result),
            "equity_curve": _normalise_core_curve(result),
        }

    variants = OrderedDict(
        [
            (BASELINE_VARIANT, _run_variant(core_results=core_results, exp100=exp100)),
            (
                PROMOTION_VARIANT,
                _run_variant(core_results=core_results, exp100=filtered),
            ),
        ]
    )
    for label, count in excluded_counts.items():
        variants[PROMOTION_VARIANT]["by_window"][label][
            "excluded_10k_candidate_count"
        ] = count
    before = variants[BASELINE_VARIANT]
    after = variants[PROMOTION_VARIANT]
    gate = _gate(after, before)
    decision = (
        "accepted_default_off_exclude_10k_financial_report_t1"
        if gate["passed"]
        else "rejected_exclude_10k_financial_report_t1"
    )

    payload: dict[str, Any] = {
        "after_metrics": after["by_window"],
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows for core baseline, "
            "plus production paper-sleeve replay over the same OHLCV snapshots. "
            "Core replay uses REPLAY_PARTIAL_REDUCES and REGIME_AWARE_EXIT."
        ),
        "before_metrics": before["by_window"],
        "change_type": "alpha_search_event_quality_filter",
        "changed_variable": "sec_financial_report_t1_form_base_eligibility",
        "decision": decision,
        "delta_metrics": {
            "aggregate": gate["aggregate_delta"],
            "by_window": gate["window_checks"],
        },
        "excluded_10k_candidate_count": excluded_counts,
        "experiment_id": EXPERIMENT_ID,
        "gate": gate,
        "hypothesis": (
            "Inside the accepted max-3 default-off SEC financial-report T+1 paper "
            "sleeve, 10-K periodic-report rows are lower-quality continuation "
            "events than earnings 8-K and 10-Q rows, so excluding them should "
            "improve three-window replacement value and drawdown."
        ),
        "lane": "alpha_search",
        "llm_metrics": {"used_llm": False, "llm_role_changed": False},
        "parameters": {
            "baseline_form_base_eligibility": "8-K, 10-Q, 10-K",
            "candidate_form_base_eligibility": "8-K, 10-Q",
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
            "alters_signal_generation": True,
            "alters_sizing": False,
            "alters_candidate_ranking": False,
            "default_off_paper_only": True,
            "live_orders_changed": False,
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate-pool/event quality: exclude weaker 10-K rows from "
                "the SEC financial-report T+1 paper queue."
            ),
            "2_history_check": (
                "exp-20260510-027 excluded platform cohort; exp-20260511-112 "
                "tested capacity. No recorded experiment isolated 10-K form-base "
                "eligibility inside this queue."
            ),
            "3_single_causal_variable": "form_base eligibility only",
            "4_acceptance_standard": (
                "Three fixed windows, aggregate EV and sleeve PnL improve, no "
                "EV-regression windows, and max drawdown does not worsen."
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
        "single_causal_variable": "sec_financial_report_t1_form_base_eligibility",
        "status": "accepted_candidate" if gate["passed"] else "rejected",
        "timestamp": now,
        "variants": variants,
    }
    payload["rejection_reason"] = (
        None
        if gate["passed"]
        else "Excluding 10-K rows did not clear the three-window event-quality gate."
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
            "Promote via shared SEC queue qualification plus focused no-orders tests."
            if gate["passed"]
            else "Do not exclude 10-K rows without forward replacement-value evidence."
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
            "Shared queue promotion and forward default-off paper observation."
            if gate["passed"]
            else "Forward out-of-sample replacement-value evidence by form_base."
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
