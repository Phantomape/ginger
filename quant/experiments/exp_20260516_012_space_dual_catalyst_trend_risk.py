"""exp-20260516-012: Space dual-catalyst source-diversity trend risk.

Tests one allocation variable on top of accepted exp-20260515-044: whether
source-diverse official Space trend signals whose event profile contains both
customer demand validation and government budget validation deserve a distinct
default-off risk scalar.

The experiment keeps the official Space pool, entries, exits, ranking, LLM/news
boundary, and live Space slots fixed.
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

import exp_20260515_048_space_source_diversity_authority_no_company_trend_risk as exp048
import exp_20260516_008_space_same_theme_confirmed_near_perfect_peer_nonleader_trend_risk as exp008


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260516-012"
STEM = "space_dual_catalyst_source_diversity_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260515-044"
BEFORE_STEM = "space_source_diversity_peer_nonleader_near_perfect_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
TARGET_EVENT_FIELDS = ("customer_win", "government_space_contract")
MARKER = "space_dual_catalyst_source_diversity_trend_risk"
SCALARS = (1.0, 1.0125, 1.025, 1.05)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(value: Any) -> Any:
    return exp048._safe(value)


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


def _is_dual_catalyst_profile(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    event_fields = {str(item) for item in profile.get("event_fields") or []}
    return set(TARGET_EVENT_FIELDS).issubset(event_fields)


def _field_check_dual_catalyst_profiles() -> dict[str, Any]:
    base = exp048.exp041.source_diversity_exp._field_check_source_diversity_profile()
    path = ROOT / "data" / "space_catalyst_event_seeds.jsonl"
    if not path.exists():
        return {**base, "passed": False, "target_profile_check": "missing_file"}

    profiles: dict[str, dict[str, set[Any]]] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not exp048.exp041.source_diversity_exp._is_non_attention_official_event(row):
            continue
        for ticker in row.get("tickers") or []:
            ticker = str(ticker).upper()
            if ticker not in exp048.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS:
                continue
            profile = profiles.setdefault(
                ticker,
                {
                    "event_ids": set(),
                    "event_fields": set(),
                    "semantic_buckets": set(),
                    "source_types": set(),
                },
            )
            profile["event_ids"].add(row.get("event_id"))
            profile["event_fields"].update(row.get("event_fields") or [])
            profile["semantic_buckets"].add(row.get("semantic_bucket"))
            profile["source_types"].add(row.get("source_type"))

    safe_profiles = {
        ticker: {key: sorted(value) for key, value in profile.items()}
        for ticker, profile in profiles.items()
    }
    target_profiles = {
        ticker: profile
        for ticker, profile in safe_profiles.items()
        if _is_dual_catalyst_profile(profile)
    }
    return {
        **base,
        "passed": bool(base.get("passed")) and bool(target_profiles),
        "target_event_fields": list(TARGET_EVENT_FIELDS),
        "target_profiles": target_profiles,
        "target_tickers": sorted(target_profiles),
    }


def _run_dual_catalyst_variant(
    label: str,
    *,
    dual_catalyst_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_predicate = exp048._is_authority_no_company_profile
    original_marker = exp048.MARKER
    exp048._is_authority_no_company_profile = _is_dual_catalyst_profile
    exp048.MARKER = MARKER
    try:
        variant = exp048._run_current_stack_variant(
            label,
            authority_no_company_scalar=dual_catalyst_scalar,
            gates=gates,
        )
    finally:
        exp048._is_authority_no_company_profile = original_predicate
        exp048.MARKER = original_marker

    variant["parameters"] = {
        **variant["parameters"],
        "space_dual_catalyst_source_diversity_trend_scalar": dual_catalyst_scalar,
        "target_strategy": TARGET_STRATEGY,
        "target_event_fields": list(TARGET_EVENT_FIELDS),
    }
    variant["space_dual_catalyst_counts"] = variant.pop(
        "source_diversity_authority_no_company_counts",
        {},
    )
    variant["space_dual_catalyst_counts_by_window"] = variant.pop(
        "source_diversity_authority_no_company_counts_by_window",
        {},
    )
    variant["space_dual_catalyst_adjustment_summary"] = variant.pop(
        "source_diversity_authority_no_company_adjustment_summary",
        {},
    )
    variant["space_dual_catalyst_adjustment_sample"] = variant.pop(
        "source_diversity_authority_no_company_adjustment_sample",
        [],
    )
    return variant


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    original_marker = exp048.MARKER
    exp048.MARKER = MARKER
    variant["source_diversity_authority_no_company_counts"] = variant.get(
        "space_dual_catalyst_counts",
        {},
    )
    try:
        gate = exp048._gate_variant(variant, before)
    finally:
        exp048.MARKER = original_marker
        variant.pop("source_diversity_authority_no_company_counts", None)

    gate["eligible_dual_catalyst_signal_count"] = gate.pop(
        "eligible_authority_no_company_signal_count",
        0,
    )
    gate["changed_dual_catalyst_signal_count"] = gate.pop(
        "changed_authority_no_company_signal_count",
        0,
    )
    return gate


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            key: row["metrics"].get(key)
            for key in (
                "worst_trade_pct",
                "max_consecutive_losses",
                "tail_loss_share",
            )
        }
        for label, row in variant["by_window"].items()
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    selected_scalar = best["parameters"][
        "space_dual_catalyst_source_diversity_trend_scalar"
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_dual_catalyst_source_diversity_trend_scalar",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": selected_scalar,
            "target_strategy": TARGET_STRATEGY,
            "target_event_fields": list(TARGET_EVENT_FIELDS),
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in exp048.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": best["aggregate"],
        "by_window_before_metrics": {
            label: item["metrics"] for label, item in before["by_window"].items()
        },
        "by_window_after_metrics": {
            label: item["metrics"] for label, item in best["by_window"].items()
        },
        "by_window_delta": gate["by_window_delta_vs_before"],
        "expected_value_score_delta": gate["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "total_pnl_delta": gate["aggregate_delta_vs_before"].get("total_pnl_sum"),
        "risk_distribution": {
            "before": _risk_distribution(before),
            "after": _risk_distribution(best),
        },
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Risk allocation: source-diverse official Space trend signals "
                "with both customer_win and government_space_contract may be "
                "mis-sized."
            ),
            "2_prior_similar_experiments": [
                "exp-20260513-012 accepted broad multi-event catalyst depth.",
                "exp-20260513-038 accepted broad source-diversity risk.",
                "exp-20260515-024 accepted source-diversity peer-nonleader trend risk.",
                "exp-20260515-044 accepted near-perfect TQS inside source-diversity peer-nonleader trend.",
                "exp-20260515-045 and exp-20260515-048 rejected one-sided company-release / authority-no-company source splits.",
                "No prior current-stack run isolated dual customer plus government catalyst event fields.",
            ],
            "3_single_causal_variable": (
                "Only the dual-catalyst source-diversity trend scalar changes."
            ),
            "4_success_criteria": (
                "Aggregate EV/PnL positive, at least two EV-improved windows, "
                "no EV-regressed windows, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, trade count >= 50, and adjusted cohort nonzero."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_012_space_dual_catalyst_trend_risk.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: dual customer plus government catalyst allocation "
            "did not improve the fixed windows while satisfying PnL and "
            "drawdown guardrails."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry adjacent Space dual-catalyst source-diversity scalars "
            "on these frozen windows without broader closed forward rows or a "
            "new production-visible catalyst-quality field."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "Accepted helper must be promoted only through shared "
                "space_catalyst_sleeve.py policy and parity tests; live Space "
                "slots remain zero."
                if promoted
                else "Experiment-only monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "Mature-satcom, GSAT, and ETF candidate-pool expansion failed on "
            "old_thin or all windows, and LLM soft-ranking lacks attribution. "
            "This keeps the fixed pool and tests one production-visible "
            "catalyst-quality field."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space dual-catalyst source-diversity trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_dual_catalyst_source_diversity_trend_scalar` on top of "
            f"accepted `{BEFORE_EXPERIMENT_ID}`."
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
        f"- dual catalyst profile field check passed: `{payload['dual_profile_field_check']['passed']}`",
        f"- target event fields: `{list(TARGET_EVENT_FIELDS)}`",
        f"- target tickers: `{payload['dual_profile_field_check'].get('target_tickers')}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no filter was added; this is a sizing-only scalar.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = best["by_window"][label]["metrics"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Best Variant",
            f"- scalar: `{best['parameters']['space_dual_catalyst_source_diversity_trend_scalar']}`",
            f"- eligible signals: `{gate['eligible_dual_catalyst_signal_count']}`",
            f"- adjusted signals: `{gate['changed_dual_catalyst_signal_count']}`",
            f"- adjusted counts: `{best['space_dual_catalyst_counts']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- max drawdown pct max delta: `{gate['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
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
    best = payload["best_variant"]
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Dual-catalyst Space scalar "
            f"{best['parameters']['space_dual_catalyst_source_diversity_trend_scalar']} "
            f"changed {gate['changed_dual_catalyst_signal_count']} signals with "
            "aggregate EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    exp008._install_experiment_path_compat()
    core = exp048.exp041.source_diversity_exp._run_core_baseline()
    gates = exp048.exp021._collect_gates()
    field_check = exp048.exp051._open_position_field_check()
    dual_profile_field_check = _field_check_dual_catalyst_profiles()
    if not field_check["passed"]:
        raise RuntimeError(f"Open-position field check failed: {field_check}")
    if not dual_profile_field_check["passed"]:
        raise RuntimeError(
            f"Dual-catalyst profile field check failed: {dual_profile_field_check}"
        )

    variants = [
        _run_dual_catalyst_variant(
            label=f"{STEM}_{str(scalar).replace('.', '_')}",
            dual_catalyst_scalar=scalar,
            gates=gates,
        )
        for scalar in SCALARS
    ]
    before = variants[0]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)
    accepted = [variant for variant in variants if variant["gate"]["passed"]]
    if accepted:
        best = max(
            accepted,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    decision = "accept" if best["gate"]["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "core_baseline": core,
        "gates": gates,
        "field_check": field_check,
        "dual_profile_field_check": dual_profile_field_check,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_scalar": [
            {
                "scalar": variant["parameters"][
                    "space_dual_catalyst_source_diversity_trend_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "hypothesis": (
            "Source-diverse official Space trend signals whose event profile "
            "contains both customer demand validation and government budget "
            "validation may deserve a distinct default-off allocation scalar."
        ),
        "changed_variable": "space_dual_catalyst_source_diversity_trend_scalar",
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
    best = payload["best_variant"]
    gate = payload["gate_results"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_scalar": best["parameters"][
                        "space_dual_catalyst_source_diversity_trend_scalar"
                    ],
                    "eligible_signals": gate["eligible_dual_catalyst_signal_count"],
                    "adjusted_signals": gate["changed_dual_catalyst_signal_count"],
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
