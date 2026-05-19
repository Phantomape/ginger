"""exp-20260516-010: Space forward-cash satcom fallback pool.

Tests one candidate-pool alpha variable on top of the accepted
exp-20260515-044 Space stack: admit only the satellite-connectivity names whose
latest forward defense-budget ledger rows have positive 5d and 10d cash PnL,
and only as trend_long fallback exposure on dates with no base official Space
signal.

This avoids another LLM soft-ranking probe, avoids broad/noisy ticker admission,
and keeps entries, exits, ranking, sizing rules, LLM/news, and live Space slots
unchanged outside the experiment-only candidate membership scope.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260515_013_space_fast_5d_satcom_candidate_pool as exp013
import exp_20260515_029_space_current_stack_fast_5d_satcom_trend_pool as exp029
import exp_20260515_035_space_vsat_same_theme_satcom_trend_fallback_pool as exp035
import exp_20260516_008_space_same_theme_confirmed_near_perfect_peer_nonleader_trend_risk as exp008


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260516-010"
STEM = "space_forward_cash_satcom_fallback_pool"
BEFORE_EXPERIMENT_ID = "exp-20260515-044"
BEFORE_STEM = "space_source_diversity_peer_nonleader_near_perfect_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
SPACE_LEDGER = (
    ROOT
    / "data"
    / "paper_sleeves"
    / "space_catalyst"
    / "event_state_shadow_ledger.jsonl"
)

TARGET_STRATEGY = "trend_long"
TARGET_SEMANTIC_BUCKET = "defense_budget_theme"
TARGET_THEME_SEGMENT = "satellite_connectivity"
TARGET_ADDED_TICKERS = ("IRDM", "VSAT")


def _safe(value: Any) -> Any:
    return exp008._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n",
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


def _metric(row: dict[str, Any], horizon: str, name: str) -> Any:
    return ((row.get("horizons") or {}).get(horizon) or {}).get(name)


def _latest_forward_rows() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line in SPACE_LEDGER.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("semantic_bucket") != TARGET_SEMANTIC_BUCKET:
            continue
        if row.get("theme_segment") != TARGET_THEME_SEGMENT:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        current = latest.get(ticker)
        if current is None or str(row.get("asof_date") or "") > str(
            current.get("asof_date") or ""
        ):
            latest[ticker] = row
    return latest


def _forward_cash_satcom_gate() -> dict[str, Any]:
    latest = _latest_forward_rows()
    rows: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    failed: list[str] = []
    for ticker in TARGET_ADDED_TICKERS:
        row = latest.get(ticker)
        if not row:
            missing.append(ticker)
            continue
        five_day_cash = _metric(row, "5d", "cash_relative_pnl")
        ten_day_cash = _metric(row, "10d", "cash_relative_pnl")
        record = {
            "asof_date": row.get("asof_date"),
            "ticker": ticker,
            "event_id": row.get("event_id"),
            "event_date": row.get("event_date"),
            "closed_decision": row.get("closed_decision"),
            "outcome_status": row.get("outcome_status"),
            "5d_cash_relative_pnl": five_day_cash,
            "10d_cash_relative_pnl": ten_day_cash,
            "10d_same_theme_replacement_value": _metric(
                row, "10d", "same_theme_replacement_value"
            ),
            "10d_spy_relative_value": _metric(row, "10d", "spy_relative_value"),
            "10d_ufo_relative_value": _metric(row, "10d", "ufo_relative_value"),
        }
        rows[ticker] = record
        if not (
            row.get("closed_decision")
            and isinstance(five_day_cash, (int, float))
            and isinstance(ten_day_cash, (int, float))
            and five_day_cash > 0.0
            and ten_day_cash > 0.0
        ):
            failed.append(ticker)
    return {
        "passed": not missing and not failed,
        "target_semantic_bucket": TARGET_SEMANTIC_BUCKET,
        "target_theme_segment": TARGET_THEME_SEGMENT,
        "target_tickers": list(TARGET_ADDED_TICKERS),
        "criteria": "closed defense-budget satellite-connectivity rows with positive 5d and 10d cash PnL",
        "rows": rows,
        "missing_tickers": missing,
        "failed_tickers": failed,
        "path": str(SPACE_LEDGER),
    }


def _collect_gates_with_pool(tickers: tuple[str, ...]) -> dict[str, Any]:
    with exp013._official_space_pool(tickers):
        gates = exp008.exp021._collect_gates()
    gates["official_space_pool"] = list(tickers)
    gates["forward_cash_satcom_gate"] = _forward_cash_satcom_gate()
    return gates


def _run_current_stack_with_pool(
    label: str,
    *,
    tickers: tuple[str, ...],
    gates: dict[str, Any],
    added_tickers: tuple[str, ...] = (),
    base_tickers: tuple[str, ...] = (),
) -> dict[str, Any]:
    fallback_summary: dict[str, Any] | None = None
    with exp013._official_space_pool(tickers):
        if added_tickers:
            with exp035._trend_fallback_extension_scope(
                added_tickers, base_tickers
            ) as scope:
                variant = exp008._run_current_stack_variant(
                    label,
                    confirmed_scalar=1.0,
                    gates=gates,
                )
            fallback_summary = exp035._fallback_filter_summary(scope)
        else:
            variant = exp008._run_current_stack_variant(
                label,
                confirmed_scalar=1.0,
                gates=gates,
            )

    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "official_space_pool": list(tickers),
        "base_official_space_pool": list(base_tickers),
        "forward_cash_satcom_fallback_added_tickers": list(added_tickers),
        "forward_cash_satcom_allowed_strategy": TARGET_STRATEGY
        if added_tickers
        else None,
    }
    if fallback_summary is not None:
        variant["forward_cash_satcom_trend_fallback_filter"] = fallback_summary
    return variant


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    gate = exp029._gate(after, before, added_tickers=TARGET_ADDED_TICKERS)
    counts = (
        (after.get("forward_cash_satcom_trend_fallback_filter") or {}).get("counts")
        or {}
    )
    gate["fallback_filter_counts"] = counts
    gate["fallback_kept_extension_signal_count"] = int(
        counts.get("kept_extension_signal", 0)
    )
    gate["fallback_filtered_official_same_day_signal_count"] = int(
        counts.get("filtered_extension_official_same_day_signal", 0)
    )
    gate["non_trend_filtered_extension_signal_count"] = int(
        counts.get("filtered_extension_non_trend_signal", 0)
    )
    gate["reasons"]["fallback_signals_present"] = (
        gate["fallback_kept_extension_signal_count"] > 0
    )
    return gate


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return exp029._risk_distribution(variant)


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_forward_cash_satcom_trend_fallback_pool_membership",
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "base_official_space_pool": payload["base_official_space_pool"],
            "extended_official_space_pool": payload["extended_official_space_pool"],
            "added_tickers": payload["added_tickers"],
            "allowed_strategy_for_added_tickers": TARGET_STRATEGY,
            "fallback_rule": (
                "allow added ticker only when no base official Space signal is "
                "present on the same signal date"
            ),
            "forward_gate": payload["forward_cash_satcom_gate"],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in exp008.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": after["aggregate"],
        "by_window_before_metrics": {
            label: row["metrics"] for label, row in before["by_window"].items()
        },
        "by_window_after_metrics": {
            label: row["metrics"] for label, row in after["by_window"].items()
        },
        "by_window_delta": gate["by_window_delta_vs_before"],
        "expected_value_score_delta": gate["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": gate["aggregate_delta_vs_before"]["total_pnl_sum"],
        "risk_distribution": {
            "before": _risk_distribution(before),
            "after": _risk_distribution(after),
        },
        "extension_trade_attribution": gate["extension_trade_attribution"],
        "fallback_filter": after.get("forward_cash_satcom_trend_fallback_filter"),
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Candidate-pool alpha: forward-positive defense-budget satcom "
                "tickers may add replacement value only as non-displacing "
                "trend fallback exposure."
            ),
            "2_prior_similar_experiments": [
                "exp-20260515-029 rejected current-stack IRDM/VSAT trend-only admission because old_thin regressed and drawdown worsened.",
                "exp-20260515-035 rejected VSAT-only fallback on exp-20260515-024.",
                "exp-20260516-008 rejected another near-perfect peer-nonleader interaction; this run changes mechanism to candidate-pool fallback on current exp-20260515-044.",
            ],
            "3_single_causal_variable": (
                "Only IRDM/VSAT forward-cash satcom fallback membership changes; "
                "base pool, entries, exits, ranking, risk scalars, LLM/news, and "
                "live slots stay fixed."
            ),
            "4_success_criteria": (
                "Extension trades present, aggregate EV/PnL positive, at least "
                "two EV-improved windows, no EV-regressed windows, max drawdown "
                "drift <= 0.5 pp, survival >= 5%, and trade count >= 50."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_010_space_forward_cash_satcom_fallback_pool.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: forward-cash IRDM/VSAT fallback admission did not "
            "improve the fixed three-window protocol without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry mature satcom candidate-pool expansion on these frozen "
            "windows without new closed forward rows, HAWK-length historical "
            "coverage, or a stronger production-visible catalyst-quality field."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If accepted, membership must be promoted through shared "
                "space_catalyst_sleeve.py and production observe-only wiring."
                if promoted
                else "Experiment-only official-pool monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking still lacks dense attribution, HAWK has short IPO "
            "history, and recent Space scalar interactions are sample-limited. "
            "This tests the remaining production-readable pool improvement: "
            "forward-positive satcom fallback exposure."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space forward-cash satcom fallback pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_forward_cash_satcom_trend_fallback_pool_membership` on top "
            f"of accepted `{BEFORE_EXPERIMENT_ID}`."
        ),
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        f"- aggregate before max drawdown pct max: `{before['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- forward-cash satcom gate passed: `{payload['forward_cash_satcom_gate']['passed']}`",
        f"- added tickers: `{payload['added_tickers']}`",
        f"- forward rows: `{payload['forward_cash_satcom_gate']['rows']}`",
        f"- fallback kept extension signals: `{gate['fallback_kept_extension_signal_count']}`",
        f"- official-same-day extension signals filtered: `{gate['fallback_filtered_official_same_day_signal_count']}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{after['aggregate']['min_survival_rate']}`",
        "- this is a candidate-scope membership test, not a new core filter.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = after["by_window"][label]["metrics"]
        extension = gate["extension_trade_attribution"][label]["trade_count"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} | {extension} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
                extension=extension,
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- max drawdown pct max delta: `{gate['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
            f"- extension trades: `{gate['extension_trade_count']}`",
            f"- fallback filter counts: `{gate['fallback_filter_counts']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(promoted).lower()}",
            f"  backtester_adapter_changed: {str(promoted).lower()}",
            f"  run_adapter_changed: {str(promoted).lower()}",
            f"  replay_only: {str(not promoted).lower()}",
            f"  parity_test_added: {str(promoted).lower()}",
            "  live_slots: 0",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "IRDM/VSAT forward-cash fallback pool "
            f"{payload['decision']} with EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    completed_at = datetime.now(timezone.utc).isoformat()
    exp008._install_experiment_path_compat()

    base_pool = tuple(exp008.exp037.OFFICIAL_SPACE_TICKERS)
    added = tuple(ticker for ticker in TARGET_ADDED_TICKERS if ticker not in base_pool)
    extended_pool = tuple(sorted(set(base_pool) | set(added)))

    forward_gate = _forward_cash_satcom_gate()
    field_check = exp008.exp051._open_position_field_check()
    base_gates = _collect_gates_with_pool(base_pool)
    extended_gates = _collect_gates_with_pool(extended_pool)

    before = _run_current_stack_with_pool(
        "accepted_exp044_base_pool",
        tickers=base_pool,
        gates=base_gates,
    )
    after = _run_current_stack_with_pool(
        "current_stack_forward_cash_satcom_trend_fallback_pool",
        tickers=extended_pool,
        gates=extended_gates,
        added_tickers=added,
        base_tickers=base_pool,
    )
    gate = _gate(after, before)
    decision = (
        "accept"
        if field_check["passed"] and forward_gate["passed"] and gate["passed"]
        else "reject"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "IRDM and VSAT have the newest defense-budget satellite-connectivity "
            "forward rows with positive 5d and 10d cash PnL outside the base "
            "official Space pool; they may add alpha only as trend fallback "
            "exposure when base official Space has no same-day signal."
        ),
        "base_official_space_pool": list(base_pool),
        "extended_official_space_pool": list(extended_pool),
        "added_tickers": list(added),
        "base_gates": base_gates,
        "extended_gates": extended_gates,
        "forward_cash_satcom_gate": forward_gate,
        "field_check": field_check,
        "before_variant": before,
        "after_variant": after,
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "changed_variable": "space_forward_cash_satcom_trend_fallback_pool_membership",
    }
    payload["experiment_log_record"] = _experiment_record(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{EXPERIMENT_ID}.json", _ticket(payload))
    artifact_path = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    payload = run()
    persist(payload)
    gate = payload["gate_results"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "added_tickers": payload["added_tickers"],
                    "fallback_kept_signals": gate[
                        "fallback_kept_extension_signal_count"
                    ],
                    "fallback_filtered_official_same_day_signals": gate[
                        "fallback_filtered_official_same_day_signal_count"
                    ],
                    "extension_trades": gate["extension_trade_count"],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "max_drawdown_delta": gate["aggregate_delta_vs_before"][
                        "max_drawdown_pct_max"
                    ],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                    "gate_reasons": gate["reasons"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
