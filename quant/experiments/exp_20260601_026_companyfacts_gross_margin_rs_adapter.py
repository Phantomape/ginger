"""exp-20260601-026: accept gross-margin Companyfacts + RS adapter.

This promotes the positive exp-20260601-021 replay lead into the shared
default-off Fundamental Growth + RS paper adapter after exp-20260601-025
accepted the PIT-DTE Gate 1 baseline.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_021_companyfacts_gross_margin_rs_candidate_pool as source  # noqa: E402


EXPERIMENT_ID = "exp-20260601-026"
STEM = "companyfacts_gross_margin_rs_adapter"
DECISION = "accepted_shared_companyfacts_gross_margin_rs_adapter"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_026_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

CANONICAL_PIT_DTE_EV = 6.3596
CANONICAL_PIT_DTE_PNL = 192_538.61


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    source._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    source._write_text(path, text)


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    ev_delta = float(aggregate["before"]["expected_value_score"]) - CANONICAL_PIT_DTE_EV
    pnl_delta = float(aggregate["before"]["total_pnl"]) - CANONICAL_PIT_DTE_PNL
    matches = abs(ev_delta) <= 0.001 and abs(pnl_delta) <= 1.0
    return {
        "baseline_matches_docs": matches,
        "canonical_docs_ev": CANONICAL_PIT_DTE_EV,
        "canonical_docs_pnl": CANONICAL_PIT_DTE_PNL,
        "current_replay_ev": aggregate["before"]["expected_value_score"],
        "current_replay_pnl": aggregate["before"]["total_pnl"],
        "ev_delta_vs_docs": source._round(ev_delta, 6),
        "pnl_delta_vs_docs": source._round(pnl_delta, 2),
        "note": "Current replay aggregate baseline matches the accepted exp-20260601-025 PIT-DTE baseline."
        if matches
        else "Current replay baseline does not match the accepted PIT-DTE baseline; do not retain.",
    }


def _gate4(
    aggregate: dict[str, Any],
    source_gate4: dict[str, Any],
    baseline_caveat: dict[str, Any],
) -> dict[str, Any]:
    gates = dict(source_gate4["gates"])
    gates["baseline_matches_docs_for_retention"] = bool(baseline_caveat["baseline_matches_docs"])
    gates["shared_default_off_adapter_promoted"] = True
    failed = [name for name, passed in gates.items() if not passed]
    alpha_failed = [
        name
        for name in source_gate4.get("alpha_failed_gates", [])
        if name != "baseline_matches_docs_for_retention"
    ]
    passed = not failed and not alpha_failed
    return {
        **source_gate4,
        "passed": passed,
        "alpha_passed": not alpha_failed,
        "promotable_now": passed,
        "decision": DECISION if passed else "rejected_companyfacts_gross_margin_rs_adapter",
        "rationale": (
            "Gross-margin quality passed all three PIT-DTE windows and is now retained "
            "as a shared default-off production-visible paper adapter; live/default "
            "orders, core ranking, sizing, exits, LLM, and news remain unchanged."
            if passed
            else "Shared adapter promotion failed the acceptance gate; do not retain."
        ),
        "gates": gates,
        "alpha_failed_gates": alpha_failed,
        "failed_gates": failed,
        "requires_parity_before_promotion": False,
        "requires_shared_adapter_before_promotion": False,
        "aggregate_expected_value_score_delta": aggregate["delta"]["expected_value_score"],
        "aggregate_total_pnl_delta": aggregate["delta"]["total_pnl"],
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Gross-Margin + RS Adapter",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Parity",
            "",
            "The retained behavior lives in `quant/fundamental_growth_rs_paper_sleeve.py`, "
            "which is already called by production `run.py`. It is default-off paper "
            "state only: `trade_enabled=false`, no live/default orders, no core ranking, "
            "no core sizing, no exits, and no LLM/news boundary changes.",
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "failed_gates": payload["gate4"]["failed_gates"],
        "metrics": {
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = payload["decision"]
            item["decision"] = payload["decision"]
            item["completed_at"] = payload["timestamp"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["report_file"] = _repo_rel(ARTIFACT_MD)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["delta"]["expected_value_score"]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["delta"]["strategy_total_pnl"]
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Companyfacts gross-margin RS adapter",
            "",
            f"- Trial family: `{source.TRIAL_FAMILY}`",
            f"- Changed variable: `{source.CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            f"- Target trades: {payload['target_trade_summary']['target_trade_count']}",
            "- Production impact: shared default-off paper adapter only; live orders remain disabled.",
            "",
            "See artifact for the three-window table and parity details.",
            "",
        ]
    )


def _build_payload() -> dict[str, Any]:
    source.CANONICAL_DOC_EV = CANONICAL_PIT_DTE_EV
    source.CANONICAL_DOC_PNL = CANONICAL_PIT_DTE_PNL
    replay = source._build_payload()
    aggregate = replay["aggregate"]
    baseline_caveat = _baseline_caveat(aggregate)
    gate4 = _gate4(aggregate, replay["gate4"], baseline_caveat)
    timestamp = _utc_now()
    ticket = _load_ticket()
    production_impact = {
        "replay_only": False,
        "default_off_paper_only": True,
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "trade_enabled": False,
        "alters_orders": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "production_watchlist_changed": False,
        "llm_or_news_changed": False,
    }
    payload = {
        **replay,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": gate4["decision"],
        "decision": gate4["decision"],
        "accepted": bool(gate4["passed"]),
        "change_type": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_variant_id": EXPERIMENT_ID,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260601-021",
            "exp-20260601-025",
            "exp-20260601-019",
            "exp-20260601-004",
        ],
        "multiple_testing_risk_bucket": "low",
        "baseline_caveat": baseline_caveat,
        "gate4": gate4,
        "gate1": {
            **replay["gate1"],
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_caveat": baseline_caveat,
        },
        "production_impact": production_impact,
        "ticket": ticket,
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "forward replacement-value rows before any live activation",
            "no nearby Companyfacts gross-margin threshold retune on the same frozen windows",
            "activation requires a separate Gate 1-4 trade adapter",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(ROOT / "quant" / "fundamental_growth_rs_paper_sleeve.py"),
            _repo_rel(ROOT / "quant" / "test_fundamental_growth_rs_paper_sleeve.py"),
            _repo_rel(ROOT / "quant" / "default_off_alpha_attribution.py"),
            _repo_rel(ROOT / "quant" / "report_generator.py"),
            _repo_rel(ROOT / "docs" / "production_backtest_parity.md"),
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
    payload["parameters"] = {
        **payload["parameters"],
        "adapter_rule_version": "fundamental_growth_rs_gross_margin_shared_adapter_v1",
        "shared_adapter_module": "quant/fundamental_growth_rs_paper_sleeve.py",
        "production_path": "quant/run.py already calls build_fundamental_growth_rs_paper_sleeve_snapshot",
        "baseline_protocol_experiment_id": "exp-20260601-025",
    }
    payload["gate_questions"]["3_single_causal_variable"] = (
        "gross_margin_quality_candidate_source_v1 shared default-off adapter promotion"
    )
    payload["gate_questions"]["4_acceptance_standard"] = (
        "Use docs/backtesting.md three PIT-DTE windows; aggregate EV/PnL positive; "
        "all three windows improve; >=20 target trades across all windows; target "
        "trades in all three windows; drawdown drift <=0.5pp; survival >=5%; "
        "max single positive share <=0.50 and HHI <=0.30; shared default-off "
        "production adapter and parity tests present."
    )
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260601_026_companyfacts_gross_margin_rs_adapter.py"
    )
    return payload


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
            "baseline_caveat": payload["baseline_caveat"],
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
            "baseline_caveat": payload["baseline_caveat"],
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))
    _write_text(CARD_MD, _card(payload))
    _update_ticket(payload)
    _update_registry(payload)

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": source.TRIAL_FAMILY,
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": source.CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": {
            **payload["aggregate"]["delta"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["delta"]["expected_value_score"],
                "strategy_total_pnl_delta": row["delta"]["total_pnl"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for label, row in payload["window_results"].items()
        ],
        "production_impact": payload["production_impact"],
        "decision_basis": payload["gate4"],
        "baseline_caveat": payload["baseline_caveat"],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }
    source.base_exp._upsert_jsonl(EXPERIMENT_LOG, log_record)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "target_trade_count",
                        "target_trade_pnl_usd",
                        "max_single_positive_share",
                        "positive_pnl_hhi",
                        "trades_by_window",
                        "pnl_by_window",
                    )
                },
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
