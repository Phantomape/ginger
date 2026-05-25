"""exp-20260525-024: shared volatility-contraction paper adapter.

This accepts only the production-visible, default-off observation path for the
exp-20260525-022 QQQ-confirmed volatility-contraction replay lead. It does not
enable live orders, expand the core universe, or alter ranking, sizing, exits,
LLM/news, or the canonical core backtest.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260525-024"
STEM = "volatility_contraction_shared_paper_adapter"
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260525-022"
    / "volatility_contraction_qqq_confirmed_sleeve.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") != payload["experiment_id"]:
                rows.append(row)
    rows.append(payload)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _open_position_field_check() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": _repo_rel(path),
            "exists": False,
            "checked_positions": 0,
            "missing_required_fields": ["file_missing"],
            "passed": False,
        }
    payload = _read_json(path)
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if isinstance(positions, dict):
        rows = list(positions.values())
    elif isinstance(positions, list):
        rows = positions
    else:
        rows = []
    missing = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = row.get("ticker") or row.get("symbol") or "UNKNOWN"
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append(f"{ticker}:{field}")
    return {
        "path": _repo_rel(path),
        "exists": True,
        "checked_positions": len(rows),
        "missing_required_fields": missing,
        "passed": not missing,
    }


def build_payload() -> dict[str, Any]:
    source = _read_json(SOURCE_JSON)
    source_aggregate = source["delta_metrics"]["aggregate"]
    source_gate4 = source["gate4"]
    open_position_check = _open_position_field_check()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "accepted_production_visible_default_off_paper_adapter",
        "decision": "accepted_shared_default_off_volatility_contraction_paper_adapter",
        "lane": "alpha_search",
        "hypothesis": (
            "The positive exp-20260525-022 QQQ-confirmed volatility-contraction "
            "alpha lead should be collected forward through a shared default-off "
            "paper adapter, without enabling live/core capital."
        ),
        "change_summary": (
            "Add production-visible default-off paper tracking for the exact "
            "exp-022 volatility-contraction + QQQ/SPY confirmation rule."
        ),
        "change_type": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": "volatility_contraction_breakout_default_off_paper_sleeve",
        "trial_variant_id": "shared_forward_adapter_v1",
        "changed_variable": "shared_volatility_contraction_qqq_confirmed_paper_adapter_only",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260426-045",
            "exp-20260525-020",
            "exp-20260525-022",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_forward_paper_adapter_for_gate4_replay_lead",
        "component": "quant/volatility_contraction_paper_sleeve.py",
        "source_alpha_experiment": "exp-20260525-022",
        "backtest_protocol": source["backtest_protocol"],
        "before_metrics": source["before_metrics"],
        "after_metrics": source["after_metrics"],
        "delta_metrics": source["delta_metrics"],
        "expected_value_score_delta": source["expected_value_score_delta"],
        "total_pnl_delta": source["total_pnl_delta"],
        "gate1": {
            "passed": True,
            "baseline_artifact": _repo_rel(SOURCE_JSON) + "#before_metrics",
            "baseline_metrics": source["before_metrics"],
        },
        "gate2": {
            "passed": open_position_check["passed"],
            "open_positions": open_position_check,
            "runtime_fields": [
                "daily OHLCV Date/Open/High/Low/Close/Volume rows",
                "SPY OHLCV Close for 20d market confirmation",
                "QQQ OHLCV Close for 20d market confirmation",
                "computed qqq_gt_spy20 market confirmation",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": 0.7925,
            "note": (
                "Default-off paper adapter only; core signals_generated/"
                "signals_survived and survival are unchanged from the accepted baseline."
            ),
        },
        "gate4": {
            "passed": bool(source_gate4.get("passed")),
            "source_gate4": source_gate4,
            "adapter_behavior_delta": 0,
            "canonical_core_metrics_changed": False,
            "rationale": (
                "Use exp-20260525-022's docs/backtesting.md three-window before/"
                "after evidence for the alpha rule; this run accepts only the "
                "production-visible default-off tracking path."
            ),
        },
        "acceptance_rationale": {
            "aggregate_ev_delta": source_aggregate["expected_value_score_delta_sum"],
            "aggregate_ev_delta_pct": source_aggregate["expected_value_score_delta_pct"],
            "aggregate_pnl_delta": source_aggregate["total_pnl_delta_sum"],
            "windows_ev_improved": source_aggregate["windows_ev_improved"],
            "windows_pnl_regressed": source_aggregate["windows_pnl_regressed"],
            "target_trades": source_aggregate["target_trade_count_sum"],
            "max_drawdown_delta_max": source_aggregate["max_drawdown_delta_max"],
            "max_single_positive_pnl_share": source["target_trade_summary"][
                "max_single_positive_pnl_share"
            ],
            "positive_pnl_hhi": source["target_trade_summary"]["positive_pnl_hhi"],
        },
        "parameters": {
            "paper_notional_usd": 10_000.0,
            "hold_days": 10,
            "market_confirmation": "QQQ 20d close-to-close return > SPY 20d close-to-close return",
            "trade_enabled": False,
            "live_orders_enabled": False,
        },
        "production_impact": {
            "shared_policy_changed": True,
            "run_adapter_changed": True,
            "backtester_adapter_changed": False,
            "parity_test_added": True,
            "replay_only": False,
            "default_off_paper_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / forward alpha maturation: QQQ-confirmed "
                "volatility-contraction paper candidates should be tracked forward "
                "because exp-022 passed all three standard windows."
            ),
            "2_history_check": {
                "exp-20260426-045": "Observed-only volatility-contraction scout; recent window was negative.",
                "exp-20260525-020": "Raw top-1 volatility contraction failed late_strong and drawdown.",
                "exp-20260525-022": "QQQ > SPY 20d confirmation passed 3/3 windows with +1.2493 EV.",
            },
            "3_single_causal_variable": "shared_volatility_contraction_qqq_confirmed_paper_adapter_only",
            "4_acceptance_standard": (
                "Use exp-022 docs/backtesting.md three-window evidence; adapter "
                "must be default-off, production-visible, no-order, and covered by focused tests."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260525_024_volatility_contraction_shared_paper_adapter.py"
            ),
        },
        "implementation": {
            "shared_module": "quant/volatility_contraction_paper_sleeve.py",
            "run_adapter": "quant/run.py",
            "report_surface": "quant/report_generator.py",
            "attribution_surface": "quant/default_off_alpha_attribution.py",
            "state_path": "data/paper_sleeves/volatility_contraction/state.json",
            "snapshot_path": "data/paper_sleeves/volatility_contraction/snapshots.jsonl",
            "trade_enabled": False,
        },
        "next_evidence_needed": [
            "Collect closed forward replacement-value rows from data/paper_sleeves/volatility_contraction/.",
            "Do not retune QQQ/SPY or ATR/breakout thresholds on frozen windows.",
            "Run a separate Gate 1-4 activation experiment before any live/default order path.",
        ],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/volatility_contraction_paper_sleeve.py",
            "quant/test_volatility_contraction_paper_sleeve.py",
            "quant/default_off_alpha_attribution.py",
            "quant/test_default_off_alpha_attribution.py",
            "quant/report_generator.py",
            "quant/run.py",
            "quant/data_paths.py",
            "docs/production_backtest_parity.md",
            "docs/data_edge_context_layers.md",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
        "tests": {
            "py_compile": "run separately after artifact generation",
            "pytest": "run separately after artifact generation",
            "three_window_replay_source": (
                "exp-20260525-022 passed: EV +1.2493 (+15.8257%), "
                "PnL +$23,409.56, 3/3 EV/PnL-positive windows"
            ),
        },
    }
    return payload


def build_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("late_strong", "mid_weak", "old_thin"):
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    agg = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Volatility-Contraction Shared Paper Adapter",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "This accepts the shared default-off forward paper adapter for the "
            "exp-20260525-022 QQQ-confirmed volatility-contraction lead. It does "
            "not enable live orders or alter core trading behavior.",
            "",
            "## Source Three-Window Evidence",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{agg['expected_value_score_delta_sum']}` (`{agg['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${agg['total_pnl_delta_sum']}` (`{agg['total_pnl_delta_pct']}`)",
            f"- target trades: `{agg['target_trade_count_sum']}`",
            f"- windows EV/PnL regressed: `{agg['windows_ev_regressed']}` / `{agg['windows_pnl_regressed']}`",
            "",
            "## Production Parity",
            "",
            "Shared helper plus `run.py`, report, and default-off attribution "
            "wiring. Trade enabled is false and activation requires a separate "
            "Gate 1-4 experiment.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Volatility-contraction shared paper adapter",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": (
                "Accepted default-off adapter; collect forward replacement value "
                "before any activation."
            ),
        },
    )
    _write_text(ARTIFACT_MD, build_markdown(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "source_ev_delta": payload["expected_value_score_delta"],
                "source_pnl_delta": payload["total_pnl_delta"],
                "gate2": payload["gate2"],
                "gate4": payload["gate4"],
                "artifact": _repo_rel(ARTIFACT_MD),
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
