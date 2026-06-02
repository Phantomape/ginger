"""exp-20260602-010: promote Companyfacts sector-residual support adapter.

This experiment retains the positive exp-20260602-009 replay lead only if the
same rule is available through the shared default-off Fundamental Growth + RS
paper adapter. It does not open live trading, core ranking, core sizing, exits,
LLM, news, or watchlist behavior.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from quant import broad_market_sector_map  # noqa: E402
from quant import fundamental_growth_rs_paper_sleeve as sleeve  # noqa: E402
from quant.experiments import exp_20260602_009_companyfacts_sector_residual_support as lead_exp  # noqa: E402


EXPERIMENT_ID = "exp-20260602-010"
STEM = "companyfacts_sector_residual_adapter"
TRIAL_FAMILY = "companyfacts_sector_residual_strength_support"
CHANGED_VARIABLE = "companyfacts_sector_residual_strength_support_v1_shared_adapter"
SOURCE_EXPERIMENT_ID = "exp-20260602-009"

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_010_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    return lead_exp._safe(value)


def _repo_rel(path: Path | str) -> str:
    return lead_exp._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _rows(*, base: float, step: float, days: int = 132) -> list[dict[str, Any]]:
    start = date(2026, 1, 1)
    rows: list[dict[str, Any]] = []
    for idx in range(days):
        close = base + step * idx
        rows.append(
            {
                "date": (start.toordinal() + idx),
                "open": round(close * 0.998, 4),
                "high": round(close * 1.01, 4),
                "low": round(close * 0.99, 4),
                "close": round(close, 4),
                "volume": 2_000_000.0,
            }
        )
    for row in rows:
        row["date"] = date.fromordinal(int(row["date"])).isoformat()
    return rows


def _validate_shared_adapter() -> dict[str, Any]:
    cfg = sleeve.DEFAULT_CONFIG
    sector_cache = broad_market_sector_map.load_cache()
    rows = {
        "AMD": _rows(base=80.0, step=0.34),
        "MSFT": _rows(base=200.0, step=0.02),
        "NVDA": _rows(base=120.0, step=0.02),
        "ORCL": _rows(base=90.0, step=0.02),
        "ADBE": _rows(base=300.0, step=0.02),
        "AVGO": _rows(base=400.0, step=0.02),
    }
    as_of = rows["AMD"][125]["date"]
    context = sleeve.SectorResidualIndex(rows, sector_cache).context("AMD", as_of, cfg)
    production_impact = sleeve._production_impact()
    checks = OrderedDict(
        [
            (
                "rule_version_matches_positive_replay",
                sleeve.SECTOR_RESIDUAL_RULE_VERSION == lead_exp.RULE_VERSION,
            ),
            (
                "ret20_threshold_matches_positive_replay",
                float(cfg["sector_residual_min_ret20_excess_sector"])
                == lead_exp.RET20_EXCESS_SECTOR_MIN,
            ),
            (
                "min_sector_members_matches_positive_replay",
                int(cfg["sector_residual_min_sector_members"])
                == lead_exp.MIN_SECTOR_MEMBER_RETURNS,
            ),
            (
                "support_scalar_matches_positive_replay",
                float(cfg["sector_residual_notional_scalar"]) == lead_exp.SUPPORT_SCALAR,
            ),
            ("fixture_passes_sector_residual", context.get("sector_residual_pass_v1") is True),
            (
                "fixture_support_scalar_applied",
                context.get("sector_residual_notional_scalar") == lead_exp.SUPPORT_SCALAR,
            ),
            ("shared_policy_changed", production_impact.get("shared_policy_changed") is True),
            ("run_adapter_changed", production_impact.get("run_adapter_changed") is True),
            ("parity_test_added", production_impact.get("parity_test_added") is True),
            ("replay_only_false", production_impact.get("replay_only") is False),
            ("default_off_paper_only", production_impact.get("default_off_paper_only") is True),
            ("trade_enabled_false", production_impact.get("trade_enabled") is False),
            ("orders_unchanged", production_impact.get("production_orders_changed") is False),
            ("alters_orders_false", production_impact.get("alters_orders") is False),
        ]
    )
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "fixture_context": context,
        "production_impact": production_impact,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Sector-Residual Adapter",
        "",
        f"- decision: `{payload['decision']}`",
        f"- source replay: `{SOURCE_EXPERIMENT_ID}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- shared adapter validation: `{payload['adapter_validation']['passed']}`",
        f"- failed adapter checks: `{', '.join(payload['adapter_validation']['failed_checks']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | survival after |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['after']['survival_rate']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Production/Backtest Parity",
            "",
            "The retained rule now lives in "
            "`quant/fundamental_growth_rs_paper_sleeve.py` as a shared default-off "
            "paper adapter. The adapter uses the same public sector cache, "
            "signal-day OHLCV close-to-close 20-day residual, 5-member sector "
            "floor, 3pp excess threshold, and 1.05x paper scalar as the positive "
            "replay lead. `trade_enabled` remains false and production orders are "
            "unchanged.",
            "",
            "## Gate Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
        ]
    )
    return "\n".join(lines)


def _card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Companyfacts sector-residual adapter",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            "- Production impact: shared default-off paper adapter; no live orders changed.",
            "",
        ]
    )


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "source_experiment": SOURCE_EXPERIMENT_ID,
        "failed_gates": payload["gate4"]["failed_gates"],
        "metrics": {
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "adapter_validation_passed": payload["adapter_validation"]["passed"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _build_payload() -> dict[str, Any]:
    lead_payload = lead_exp._build_payload()
    adapter_validation = _validate_shared_adapter()
    source_passed = bool(lead_payload["gate4"]["alpha_passed"])
    accepted = bool(source_passed and adapter_validation["passed"])
    decision = (
        "accepted_companyfacts_sector_residual_shared_adapter"
        if accepted
        else "rejected_companyfacts_sector_residual_shared_adapter"
    )
    gate4 = dict(lead_payload["gate4"])
    gate4["promotable_now"] = accepted
    gate4["decision"] = decision
    gate4["adapter_validation_passed"] = adapter_validation["passed"]
    gate4["failed_gates"] = list(gate4.get("failed_gates") or [])
    if not adapter_validation["passed"]:
        gate4["failed_gates"].append("shared_adapter_validation_failed")
    gate4["rationale"] = (
        "Retained: exp-20260602-009 passed the canonical three-window Gate 4, "
        "and this run promotes the exact sector-residual support into the shared "
        "default-off Fundamental Growth + RS paper adapter without changing live "
        "orders, core entry, ranking, sizing, exits, LLM, or news behavior."
        if accepted
        else "Rejected: the replay lead or shared adapter validation failed; no strategy behavior is retained."
    )
    timestamp = _utc_now()
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "lane": "alpha_search",
        "decision": decision,
        "accepted": accepted,
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "hypothesis": (
            "Risk allocation / candidate quality: among accepted Companyfacts "
            "Growth + RS paper rows, those beating their public sector median "
            "20-day return by at least 3pp deserve a small default-off paper "
            "support scalar."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "companyfacts_sector_residual_strength_support",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260525-916",
            "exp-20260601-030",
            "exp-20260602-009",
        ],
        "multiple_testing_risk_bucket": "minimal_for_promotion_moderate_for_family",
        "new_evidence_type": "shared_adapter_parity_for_positive_three_window_replay_lead",
        "parameters": {
            "rule_version": sleeve.SECTOR_RESIDUAL_RULE_VERSION,
            "min_ret20_excess_sector": sleeve.DEFAULT_CONFIG["sector_residual_min_ret20_excess_sector"],
            "min_sector_members": sleeve.DEFAULT_CONFIG["sector_residual_min_sector_members"],
            "support_scalar": sleeve.DEFAULT_CONFIG["sector_residual_notional_scalar"],
            "sector_map": _repo_rel(broad_market_sector_map.DEFAULT_CACHE_PATH),
            "source_replay_artifact": _repo_rel(lead_exp.OUT_JSON),
        },
        "before_metrics": lead_payload["before_metrics"],
        "after_metrics": lead_payload["after_metrics"],
        "delta_metrics": lead_payload["delta_metrics"],
        "aggregate": lead_payload["aggregate"],
        "baseline_context": lead_payload["baseline_context"],
        "window_results": lead_payload["window_results"],
        "target_trade_summary": lead_payload["target_trade_summary"],
        "selection_diagnostics": lead_payload["selection_diagnostics"],
        "gate1": lead_payload["gate1"],
        "gate2": {
            **lead_payload["gate2"],
            "shared_adapter_runtime_fields": [
                "data/reference/broad_market_sector_map.json sector",
                "signal-date OHLCV close",
                "20-trading-day prior OHLCV close",
                "ret20_excess_sector",
                "sector_member_return_count",
            ],
        },
        "gate3": lead_payload["gate3"],
        "gate4": gate4,
        "adapter_validation": adapter_validation,
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / candidate quality: Companyfacts paper rows "
                "with 20d sector-relative strength get a 1.05x default-off paper "
                "support scalar."
            ),
            "2_history_check": (
                "exp-20260602-009 passed all three windows but was not retained "
                "because it lacked a shared adapter; exp-20260525-916 was a "
                "broader standalone sector source and failed late_strong/drawdown."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three PIT-DTE windows, plus shared adapter "
                "validation that production and backtest use one default-off "
                "paper implementation."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260602_010_companyfacts_sector_residual_adapter.py"
            ),
        },
        "production_impact": adapter_validation["production_impact"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "ticket": _load_ticket(),
        "interpretation": gate4["rationale"],
        "related_files": [
            _repo_rel(Path(__file__)),
            "quant/fundamental_growth_rs_paper_sleeve.py",
            "quant/test_fundamental_growth_rs_paper_sleeve.py",
            "quant/default_off_alpha_attribution.py",
            "quant/report_generator.py",
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **payload["aggregate"]["before"],
            "windows": payload["before_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))
    _write_text(CARD_MD, _card(payload))
    _update_ticket(payload)
    print(json.dumps(_safe({"decision": payload["decision"], "aggregate": payload["aggregate"]["delta"]}), sort_keys=True))


if __name__ == "__main__":
    main()
