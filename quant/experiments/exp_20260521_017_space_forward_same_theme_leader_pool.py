"""exp-20260521-017: Space forward same-theme leader pool.

Tests one Space candidate-pool governance variable on the current accepted
default-off Space stack: keep only official Space candidates with mature
forward evidence of positive 10d cash, same-theme replacement, and SPY-relative
value, while allowing the previously studied VSAT extension if it passes that
same rule.

This is an alpha_search scout, not a bug repair. It does not change live Space
slots or shared production policy unless the three-window gate passes.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260516_032_space_forward_benchmark_same_theme_satcom_fallback_pool as pool
import exp_20260519_027_space_dual_catalyst_benchmark_breadth_precision_sweep as current


EXPERIMENT_ID = "exp-20260521-017"
STEM = "space_forward_same_theme_leader_pool"
CHANGED_VARIABLE = "space_forward_same_theme_leader_pool_membership"

CURRENT_ACCEPTED_EXPERIMENT_ID = "exp-20260519-027"
CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR = 1.021875

BASE_OFFICIAL_SPACE_TICKERS = tuple(pool.BASE_OFFICIAL_SPACE_TICKERS)
EXTENSION_CANDIDATE_TICKERS = ("VSAT",)
RULE_SCOPE_TICKERS = tuple(
    sorted(set(BASE_OFFICIAL_SPACE_TICKERS).union(EXTENSION_CANDIDATE_TICKERS))
)

FORWARD_LEDGER = ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
LOG_DIR = ROOT / "experiments" / "logs"
TICKET_DIR = ROOT / "experiments" / "tickets"
ARTIFACT_DIR = ROOT / "experiments" / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

MAX_WINDOW_DRAWDOWN_DAMAGE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(value: Any) -> Any:
    return current._safe(value)


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _latest_official_rows_by_event_ticker() -> dict[tuple[str, str], dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    scoped = set(RULE_SCOPE_TICKERS)
    for row in _load_jsonl(FORWARD_LEDGER):
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in scoped:
            continue
        if row.get("closed_decision") is not True:
            continue
        if row.get("semantic_bucket") == "attention_only":
            continue
        horizon = (row.get("horizons") or {}).get("10d") or {}
        if horizon.get("status") != "mature":
            continue
        event_id = str(row.get("event_id") or "")
        if not event_id:
            continue
        key = (event_id, ticker)
        prior = latest.get(key)
        if prior is None or str(row.get("asof_date") or "") >= str(
            prior.get("asof_date") or ""
        ):
            latest[key] = row
    return latest


def _forward_same_theme_leader_gate() -> dict[str, Any]:
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in _latest_official_rows_by_event_ticker().values():
        ticker = str(row.get("ticker") or "").upper()
        horizon = (row.get("horizons") or {}).get("10d") or {}
        rows_by_ticker.setdefault(ticker, []).append(
            {
                "event_id": row.get("event_id"),
                "asof_date": row.get("asof_date"),
                "event_date": row.get("event_date"),
                "semantic_bucket": row.get("semantic_bucket"),
                "source_type": row.get("source_type"),
                "theme_segment": row.get("theme_segment"),
                "cash_relative_pnl": _as_float(horizon.get("cash_relative_pnl")),
                "same_theme_replacement_value": _as_float(
                    horizon.get("same_theme_replacement_value")
                ),
                "spy_relative_value": _as_float(horizon.get("spy_relative_value")),
            }
        )

    profiles: dict[str, dict[str, Any]] = {}
    passed_tickers: list[str] = []
    for ticker in sorted(RULE_SCOPE_TICKERS):
        rows = rows_by_ticker.get(ticker, [])
        cash = [row["cash_relative_pnl"] for row in rows if row["cash_relative_pnl"] is not None]
        same = [
            row["same_theme_replacement_value"]
            for row in rows
            if row["same_theme_replacement_value"] is not None
        ]
        spy = [row["spy_relative_value"] for row in rows if row["spy_relative_value"] is not None]
        passes = bool(
            cash
            and same
            and spy
            and mean(float(value) for value in cash) > 0.0
            and mean(float(value) for value in same) > 0.0
            and mean(float(value) for value in spy) > 0.0
        )
        profiles[ticker] = {
            "passes": passes,
            "closed_10d_official_event_count": len(rows),
            "avg_10d_cash_relative_pnl": (
                round(mean(float(value) for value in cash), 6) if cash else None
            ),
            "avg_10d_same_theme_replacement_value": (
                round(mean(float(value) for value in same), 6) if same else None
            ),
            "avg_10d_spy_relative_value": (
                round(mean(float(value) for value in spy), 6) if spy else None
            ),
            "rows": rows,
        }
        if passes:
            passed_tickers.append(ticker)

    return {
        "description": (
            "Candidate-pool rule: official Space candidates need mature positive "
            "10d average cash, same-theme replacement, and SPY-relative value."
        ),
        "ledger": str(FORWARD_LEDGER.relative_to(ROOT)),
        "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
        "extension_candidate_tickers": list(EXTENSION_CANDIDATE_TICKERS),
        "rule_scope_tickers": list(RULE_SCOPE_TICKERS),
        "passed_tickers": passed_tickers,
        "removed_from_base": sorted(set(BASE_OFFICIAL_SPACE_TICKERS) - set(passed_tickers)),
        "added_to_base": sorted(set(passed_tickers) - set(BASE_OFFICIAL_SPACE_TICKERS)),
        "profiles": profiles,
        "passed": bool(passed_tickers),
    }


def _open_position_field_check() -> dict[str, Any]:
    path = ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"passed": False, "path": str(path.relative_to(ROOT)), "error": "missing"}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    positions = payload if isinstance(payload, list) else payload.get("positions", [])
    missing: list[dict[str, Any]] = []
    for index, position in enumerate(positions):
        if not isinstance(position, dict):
            continue
        missing_fields = [
            field for field in ("entry_date", "target_price") if position.get(field) in (None, "")
        ]
        if missing_fields:
            missing.append(
                {
                    "index": index,
                    "ticker": position.get("ticker") or position.get("symbol"),
                    "missing_fields": missing_fields,
                }
            )
    return {
        "passed": not missing,
        "path": str(path.relative_to(ROOT)),
        "position_count": len(positions) if isinstance(positions, list) else 0,
        "missing_entry_date_or_target_price": missing,
    }


def _run_with_pool(tickers: tuple[str, ...]) -> dict[str, Any]:
    gates = pool._collect_gates_with_pool(tuple(tickers))
    with pool.prior_pool.exp013._official_space_pool(tuple(tickers)):
        result = current.prior._run_variant(
            benchmark_breadth_scalar=CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            gates=gates,
        )
    result.setdefault("parameters", {})
    result["parameters"].update(
        {
            "official_space_tickers": list(tickers),
            "accepted_before_experiment": CURRENT_ACCEPTED_EXPERIMENT_ID,
            "accepted_benchmark_breadth_scalar": CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR,
        }
    )
    return result


def _metric_rows(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {label: row["metrics"] for label, row in result["by_window"].items()}


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, float]:
    return {
        "expected_value_score": round(
            float(after.get("expected_value_score", 0.0))
            - float(before.get("expected_value_score", 0.0)),
            6,
        ),
        "total_pnl": round(
            float(after.get("total_pnl", 0.0)) - float(before.get("total_pnl", 0.0)),
            2,
        ),
        "max_drawdown_pct": round(
            float(after.get("max_drawdown_pct", 0.0))
            - float(before.get("max_drawdown_pct", 0.0)),
            6,
        ),
        "trade_count": int(after.get("trade_count", 0)) - int(before.get("trade_count", 0)),
        "signals_generated": int(after.get("signals_generated", 0))
        - int(before.get("signals_generated", 0)),
        "signals_survived": int(after.get("signals_survived", 0))
        - int(before.get("signals_survived", 0)),
        "survival_rate": round(
            float(after.get("survival_rate", 0.0)) - float(before.get("survival_rate", 0.0)),
            6,
        ),
    }


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, float]:
    return {
        "expected_value_score_sum": round(
            float(after.get("expected_value_score_sum", 0.0))
            - float(before.get("expected_value_score_sum", 0.0)),
            6,
        ),
        "total_pnl_sum": round(
            float(after.get("total_pnl_sum", 0.0))
            - float(before.get("total_pnl_sum", 0.0)),
            2,
        ),
        "max_drawdown_pct_max": round(
            float(after.get("max_drawdown_pct_max", 0.0))
            - float(before.get("max_drawdown_pct_max", 0.0)),
            6,
        ),
        "trade_count_sum": int(after.get("trade_count_sum", 0))
        - int(before.get("trade_count_sum", 0)),
        "signals_generated_sum": int(after.get("signals_generated_sum", 0))
        - int(before.get("signals_generated_sum", 0)),
        "signals_survived_sum": int(after.get("signals_survived_sum", 0))
        - int(before.get("signals_survived_sum", 0)),
        "min_survival_rate": round(
            float(after.get("min_survival_rate", 0.0))
            - float(before.get("min_survival_rate", 0.0)),
            6,
        ),
    }


def _gate(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    forward_gate: dict[str, Any],
) -> dict[str, Any]:
    by_window = {
        label: _delta(after["by_window"][label]["metrics"], row["metrics"])
        for label, row in before["by_window"].items()
    }
    aggregate = _aggregate_delta(after["aggregate"], before["aggregate"])
    ev_improved = {
        label: row["expected_value_score"]
        for label, row in by_window.items()
        if row["expected_value_score"] > 1e-9
    }
    ev_regressed = {
        label: row["expected_value_score"]
        for label, row in by_window.items()
        if row["expected_value_score"] < -1e-9
    }
    max_window_drawdown_damage = max(
        (row["max_drawdown_pct"] for row in by_window.values()),
        default=0.0,
    )
    reasons = {
        "forward_gate_passed": bool(forward_gate.get("passed")),
        "candidate_pool_changed": tuple(forward_gate["passed_tickers"])
        != tuple(BASE_OFFICIAL_SPACE_TICKERS),
        "aggregate_ev_positive": aggregate["expected_value_score_sum"] > 0.0,
        "aggregate_pnl_positive": aggregate["total_pnl_sum"] > 0.0,
        "at_least_two_ev_windows_improved": len(ev_improved) >= 2,
        "no_ev_regressed_windows": not ev_regressed,
        "max_window_drawdown_damage_lte_0_5pp": (
            max_window_drawdown_damage <= MAX_WINDOW_DRAWDOWN_DAMAGE
        ),
        "survival_rate_ok": after["aggregate"].get("min_survival_rate", 0.0)
        >= MIN_SURVIVAL_RATE,
        "trade_count_ok": after["aggregate"].get("trade_count_sum", 0) >= MIN_TRADE_COUNT,
    }
    return {
        "passed": all(reasons.values()),
        "reasons": reasons,
        "aggregate_delta": aggregate,
        "by_window_delta": by_window,
        "ev_improved_windows": ev_improved,
        "ev_regressed_windows": ev_regressed,
        "max_window_drawdown_damage": max_window_drawdown_damage,
    }


def _summary_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "aggregate": result["aggregate"],
        "windows": _metric_rows(result),
    }


def _artifact_markdown(record: dict[str, Any]) -> str:
    gate = record["gate4"]
    lines = [
        f"# {EXPERIMENT_ID} Space forward same-theme leader pool",
        "",
        f"- decision: {record['decision']}",
        f"- changed_variable: `{CHANGED_VARIABLE}`",
        f"- EV delta: `{record['expected_value_score_delta']}`",
        f"- PnL delta: `${record['total_pnl_delta']:,.2f}`",
        f"- passed tickers: `{', '.join(record['parameters']['selected_pool_tickers'])}`",
        f"- removed from base: `{', '.join(record['parameters']['removed_from_base'])}`",
        f"- added to base: `{', '.join(record['parameters']['added_to_base'])}`",
        "",
        "## Gate 4",
        "",
    ]
    for label, row in gate["by_window_delta"].items():
        lines.append(
            f"- `{label}`: EV `{row['expected_value_score']:+.4f}`, "
            f"PnL `${row['total_pnl']:+,.2f}`, DD `{row['max_drawdown_pct']:+.4f}`"
        )
    lines.extend(
        [
            "",
            "Rejected because the candidate-pool rule caused large EV regressions in "
            "`mid_weak` and `old_thin`; no shared Space policy was promoted.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> dict[str, Any]:
    completed_at = datetime.now(UTC).isoformat()
    forward_gate = _forward_same_theme_leader_gate()
    selected_pool = tuple(forward_gate["passed_tickers"])
    field_check = _open_position_field_check()

    before = _run_with_pool(BASE_OFFICIAL_SPACE_TICKERS)
    after = _run_with_pool(selected_pool)
    gate4 = _gate(before=before, after=after, forward_gate=forward_gate)
    decision = "accepted" if gate4["passed"] else "rejected"

    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": completed_at,
        "status": decision,
        "decision": (
            "accepted_space_forward_same_theme_leader_pool"
            if gate4["passed"]
            else "rejected_space_forward_same_theme_leader_pool"
        ),
        "lane": "alpha_search",
        "alpha_hypothesis": {
            "category": "candidate_pool / Space sleeve governance",
            "entry_exit_ranking_or_allocation": "candidate_pool",
            "playbook_alignment": (
                "Follows the playbook preference for replacement value and "
                "governed sleeve expansion instead of another adjacent Space scalar."
            ),
        },
        "hypothesis": (
            "Space should stop treating all official catalyst tickers as equal. A "
            "candidate pool restricted to mature 10d same-theme replacement winners, "
            "with VSAT allowed only if it passes the same production-visible forward "
            "rule, may improve Space sleeve EV while avoiding noisy satcom additions."
        ),
        "change_summary": (
            "Replace the accepted official Space pool with the forward same-theme "
            "leader pool selected from mature Space shadow-ledger outcomes."
        ),
        "change_type": "candidate_pool_governance_scout",
        "mechanism_family": "space_catalyst_candidate_pool_governance",
        "trial_family": "space_forward_replacement_candidate_pool",
        "trial_variant_id": "same_theme_leader_pool",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 12,
        "nearby_prior_experiments": [
            "exp-20260515-013",
            "exp-20260515-031",
            "exp-20260516-032",
            "exp-20260517-018",
            "exp-20260518-017",
            "exp-20260520-020",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_replacement_value_cohort",
        "parameters": {
            "anti_js": "No JavaScript was used.",
            "accepted_before_experiment": CURRENT_ACCEPTED_EXPERIMENT_ID,
            "accepted_benchmark_breadth_scalar": CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            "base_official_space_tickers": list(BASE_OFFICIAL_SPACE_TICKERS),
            "extension_candidate_tickers": list(EXTENSION_CANDIDATE_TICKERS),
            "selected_pool_tickers": list(selected_pool),
            "removed_from_base": forward_gate["removed_from_base"],
            "added_to_base": forward_gate["added_to_base"],
            "rule": (
                "Average mature official non-attention 10d cash_relative_pnl, "
                "same_theme_replacement_value, and spy_relative_value must all be > 0."
            ),
            "locked_variables": [
                "Space entry logic",
                "Space exit logic",
                "Space ranking",
                "Space risk scalar stack",
                "LLM prompt and authority",
                "news veto",
                "live Space slots",
            ],
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed three-window Space replay using frozen "
            "Space augmented snapshots, compared against accepted exp-20260519-027."
        ),
        "date_range": {
            label: spec
            for label, spec in current.prior.BASE.exp041.source_diversity_exp.WINDOWS.items()
        },
        "gate1": {
            "baseline_name": CURRENT_ACCEPTED_EXPERIMENT_ID,
            "baseline_metrics": before["aggregate"],
        },
        "gate2": {
            "passed": bool(field_check.get("passed")) and bool(forward_gate.get("passed")),
            "operator_position_field_check": field_check,
            "forward_same_theme_leader_gate": forward_gate,
            "required_fields": [
                "ticker",
                "event_id",
                "semantic_bucket",
                "source_type",
                "10d.cash_relative_pnl",
                "10d.same_theme_replacement_value",
                "10d.spy_relative_value",
                "entry_date",
                "target_price",
            ],
        },
        "gate3": {
            "passed": after["aggregate"].get("min_survival_rate", 0.0) >= MIN_SURVIVAL_RATE,
            "signals_generated_before": before["aggregate"].get("signals_generated_sum"),
            "signals_survived_before": before["aggregate"].get("signals_survived_sum"),
            "signals_generated_after": after["aggregate"].get("signals_generated_sum"),
            "signals_survived_after": after["aggregate"].get("signals_survived_sum"),
            "min_survival_before": before["aggregate"].get("min_survival_rate"),
            "min_survival_after": after["aggregate"].get("min_survival_rate"),
        },
        "gate4": gate4,
        "before_metrics": _summary_metrics(before),
        "after_metrics": _summary_metrics(after),
        "delta_metrics": {
            "aggregate": gate4["aggregate_delta"],
            "by_window": gate4["by_window_delta"],
        },
        "expected_value_score_delta": gate4["aggregate_delta"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": gate4["aggregate_delta"]["total_pnl_sum"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this experiment used only "
                "deterministic forward ledger fields."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "live_slots_changed": False,
            "live_slots": 0,
            "alters_orders": False,
            "alters_sizing": False,
            "alters_candidate_ranking": False,
        },
        "risk_of_change": (
            "No production/shared policy was changed. If promoted later, this must "
            "move into shared Space candidate-pool governance before any live slot."
        ),
        "rejection_reason": (
            "Gate 4 failed: the same-theme leader pool improved late_strong but "
            "regressed mid_weak and old_thin EV, with aggregate EV and PnL sharply lower."
            if not gate4["passed"]
            else None
        ),
        "next_retry_requires": [
            "new closed forward Space rows",
            "a non-pool catalyst-quality field that does not prune the base pool",
            "or a separate live-slot activation design after replacement-value maturity",
        ],
        "why_not_other_changes": (
            "Short-extension was rejected in exp-20260520-020; LLM soft-ranking is "
            "sample-limited; broad satcom/VSAT-only additions were already rejected. "
            "This tested candidate-pool governance directly instead of another scalar."
        ),
        "related_files": [
            "quant/experiments/exp_20260521_017_space_forward_same_theme_leader_pool.py",
            "data/experiments/exp-20260521-017/space_forward_same_theme_leader_pool.json",
            "experiments/logs/exp-20260521-017.json",
            "experiments/tickets/exp-20260521-017.json",
            "experiments/artifacts/exp-20260521-017_space_forward_same_theme_leader_pool.md",
            "docs/experiment_log.jsonl",
        ],
        "anti_js": "No JavaScript was used.",
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "record": record,
        "baseline": before,
        "variant": after,
    }
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", record)
    _write_json(
        TICKET_DIR / f"{EXPERIMENT_ID}.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "status": decision,
            "changed_variable": CHANGED_VARIABLE,
            "decision": record["decision"],
            "next_retry_requires": record["next_retry_requires"],
            "anti_js": "No JavaScript was used.",
        },
    )
    (ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        _artifact_markdown(record),
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, record)
    return record


if __name__ == "__main__":
    result = main()
    print(json.dumps(_safe(result), indent=2, ensure_ascii=False, sort_keys=True))
