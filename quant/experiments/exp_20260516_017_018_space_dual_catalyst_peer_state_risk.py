"""exp-20260516-017/018: Space dual-catalyst peer-state trend risk.

Runs two tightly scoped Space allocation experiments on top of accepted
exp-20260516-015:

- exp-20260516-017 tests dual-catalyst + peer leader confirmation.
- exp-20260516-018 tests dual-catalyst + peer nonleader confirmation.

Both keep the official Space pool, entries, exits, ranking, LLM/news boundary,
and live Space slots fixed. Only the incremental default-off allocation scalar
changes.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260516_015_space_dual_catalyst_iwm_leader_trend_risk as base


LOGGER = logging.getLogger(__name__)

DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

BEFORE_EXPERIMENT_ID = "exp-20260516-015"
BEFORE_STEM = "space_dual_catalyst_iwm_leader_trend_risk"
TARGET_STRATEGY = "trend_long"
ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR = 1.0125


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    stem: str
    marker: str
    changed_variable: str
    target_peer_state: str
    scalars: tuple[float, ...]
    hypothesis: str
    decision_if_passed: str
    rejection_reason: str
    next_evidence_needed: str


CONFIGS = (
    ExperimentConfig(
        experiment_id="exp-20260516-017",
        stem="space_dual_catalyst_peer_leader_trend_risk",
        marker="space_dual_catalyst_peer_leader_trend_risk",
        changed_variable="space_dual_catalyst_peer_leader_trend_scalar",
        target_peer_state="leader",
        scalars=(1.0, 1.0125, 1.025, 1.05),
        hypothesis=(
            "Accepted dual-catalyst source-diverse official Space trend "
            "signals may deserve another small scalar when the ticker also "
            "leads the official Space peer basket."
        ),
        decision_if_passed="accept",
        rejection_reason=(
            "Gate 4 failed: dual-catalyst peer-leader confirmation was positive "
            "but changed only one validation window, below the Space "
            "multi-window acceptance guard."
        ),
        next_evidence_needed=(
            "Do not retry nearby dual-catalyst peer-leader scalars on these "
            "frozen windows without broader closed forward rows or a different "
            "production-visible catalyst-quality field."
        ),
    ),
    ExperimentConfig(
        experiment_id="exp-20260516-018",
        stem="space_dual_catalyst_peer_nonleader_trend_risk",
        marker="space_dual_catalyst_peer_nonleader_trend_risk",
        changed_variable="space_dual_catalyst_peer_nonleader_trend_scalar",
        target_peer_state="nonleader",
        scalars=(0.95, 0.975, 1.0, 1.0125, 1.025, 1.05),
        hypothesis=(
            "Accepted dual-catalyst source-diverse official Space trend "
            "signals may still be under-sized when peer momentum is nonleader, "
            "because the customer-plus-government catalyst stack can offset "
            "peer-relative lag."
        ),
        decision_if_passed="accept",
        rejection_reason=(
            "Gate 4 failed: dual-catalyst peer-nonleader scalar did not satisfy "
            "multi-window EV/PnL, drawdown, and cohort guardrails."
        ),
        next_evidence_needed=(
            "Do not retry nearby dual-catalyst peer-nonleader scalars on these "
            "frozen windows without new closed forward rows or a materially "
            "different production-visible catalyst-quality field."
        ),
    ),
)


def _safe(value: Any) -> Any:
    return base._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_for_experiment(path: Path, payload: dict[str, Any]) -> None:
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
            if row.get("experiment_id") != payload.get("experiment_id"):
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _target_signal(config: ExperimentConfig, signal: dict[str, Any], profile: dict[str, Any] | None) -> bool:
    return (
        base.exp014._is_dual_catalyst_profile(profile)
        and str(signal.get("strategy") or "") == TARGET_STRATEGY
        and str(signal.get("space_peer_momentum_state") or "") == config.target_peer_state
    )


def _run_variant(
    config: ExperimentConfig,
    *,
    scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_scale_and_record = base.exp041.accepted_exp._scale_and_record
    near_perfect_adjustments: list[dict[str, Any]] = []
    dual_adjustments: list[dict[str, Any]] = []
    dual_iwm_adjustments: list[dict[str, Any]] = []
    peer_state_adjustments: list[dict[str, Any]] = []

    def patched_scale_and_record(
        *,
        signal: dict[str, Any],
        sizing: dict[str, Any],
        scalar: float,
        portfolio_value: float,
        marker: str,
        counts: Counter[str],
        adjustments: list[dict[str, Any]],
        profile: dict[str, Any] | None,
    ) -> None:
        original_scale_and_record(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            marker=marker,
            counts=counts,
            adjustments=adjustments,
            profile=profile,
        )
        if marker != "space_source_diversity_trend_risk":
            return
        if str(signal.get("strategy") or "") != TARGET_STRATEGY:
            return
        if not sizing:
            return
        if str(signal.get("space_peer_momentum_state") or "") == "nonleader":
            base.exp041.source_diversity_exp._scale_sizing(
                sizing,
                base.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR,
                portfolio_value,
                "space_source_diversity_peer_nonleader_trend_risk",
            )
            signal["space_source_diversity_peer_nonleader_trend_bucket"] = True
            signal["space_source_diversity_peer_nonleader_trend_scalar"] = (
                base.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR
            )
            signal["space_source_diversity_peer_nonleader_profile"] = profile
        if base.exp044._is_target_signal(signal, profile):
            base.exp044._apply_extra_scale(
                signal=signal,
                sizing=sizing,
                scalar=(
                    base.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
                ),
                portfolio_value=portfolio_value,
                counts=counts,
                adjustments=near_perfect_adjustments,
                profile=profile,
            )
            signal[
                "space_source_diversity_peer_nonleader_near_perfect_trend_bucket"
            ] = True
            signal[
                "space_source_diversity_peer_nonleader_near_perfect_trend_scalar"
            ] = base.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
            signal["space_source_diversity_peer_nonleader_near_perfect_profile"] = (
                profile
            )
        if not base.exp014._is_dual_catalyst_profile(profile):
            return
        base._apply_scale(
            signal=signal,
            sizing=sizing,
            scalar=base.ACCEPTED_DUAL_CATALYST_TREND_SCALAR,
            portfolio_value=portfolio_value,
            marker="space_dual_catalyst_source_diversity_trend_risk",
            counts=counts,
            adjustments=dual_adjustments,
            profile=profile,
        )
        signal["space_source_diversity_dual_catalyst_trend_bucket"] = True
        signal["space_source_diversity_dual_catalyst_trend_scalar"] = (
            base.ACCEPTED_DUAL_CATALYST_TREND_SCALAR
        )
        signal["space_source_diversity_dual_catalyst_profile"] = profile
        if str(signal.get("space_iwm_relative_state") or "") == "smallcap_leader":
            base._apply_scale(
                signal=signal,
                sizing=sizing,
                scalar=ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR,
                portfolio_value=portfolio_value,
                marker="space_dual_catalyst_iwm_leader_trend_risk",
                counts=counts,
                adjustments=dual_iwm_adjustments,
                profile=profile,
            )
            signal["space_dual_catalyst_iwm_leader_trend_bucket"] = True
            signal["space_dual_catalyst_iwm_leader_trend_scalar"] = (
                ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR
            )
            signal["space_dual_catalyst_iwm_leader_profile"] = profile
        if not _target_signal(config, signal, profile):
            return
        base._apply_scale(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            marker=config.marker,
            counts=counts,
            adjustments=peer_state_adjustments,
            profile=profile,
        )
        signal[f"{config.marker}_bucket"] = True
        signal[config.changed_variable] = scalar
        signal[f"{config.marker}_profile"] = profile

    base.exp041.accepted_exp._scale_and_record = patched_scale_and_record
    try:
        variant = base.exp021._run_exp051_stack_variant(
            label=f"{config.stem}_{str(scalar).replace('.', '_')}",
            defense_same_theme_winner_scalar=(
                base.ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR
            ),
            gates=gates,
        )
    finally:
        base.exp041.accepted_exp._scale_and_record = original_scale_and_record

    counts = Counter(variant.get("source_diversity_trend_counts") or {})
    by_window_counts = {
        name: {
            key: value
            for key, value in sorted(
                (row.get("source_diversity_trend_counts") or {}).items()
            )
            if config.marker in key
        }
        for name, row in variant["by_window"].items()
    }
    selected = scalar
    variant["parameters"][config.changed_variable] = selected
    variant["parameters"]["target_peer_momentum_state"] = config.target_peer_state
    variant["parameters"]["accepted_before_experiment"] = BEFORE_EXPERIMENT_ID
    variant["parameters"]["accepted_dual_catalyst_iwm_leader_trend_scalar"] = (
        ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR
    )
    variant["source_diversity_peer_nonleader_near_perfect_adjustment_summary"] = (
        base.exp041.source_diversity_exp._adjustment_summary(
            near_perfect_adjustments
        )
    )
    variant["dual_catalyst_adjustment_summary"] = (
        base.exp041.source_diversity_exp._adjustment_summary(dual_adjustments)
    )
    variant["dual_catalyst_iwm_leader_adjustment_summary"] = (
        base.exp041.source_diversity_exp._adjustment_summary(dual_iwm_adjustments)
    )
    variant["dual_catalyst_peer_state_counts"] = {
        key: value for key, value in sorted(counts.items()) if config.marker in key
    }
    variant["dual_catalyst_peer_state_counts_by_window"] = by_window_counts
    variant["dual_catalyst_peer_state_adjustment_summary"] = (
        base.exp041.source_diversity_exp._adjustment_summary(
            peer_state_adjustments
        )
    )
    variant["dual_catalyst_peer_state_adjustment_sample"] = (
        peer_state_adjustments[:25]
    )
    return variant


def _gate_variant(
    config: ExperimentConfig,
    variant: dict[str, Any],
    before: dict[str, Any],
) -> dict[str, Any]:
    aggregate_delta = base.exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        label: base.exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in variant["by_window"].items()
    }
    ev_improved = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] > 1e-9
    }
    ev_regressed = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] < -1e-9
    }
    counts = variant.get("dual_catalyst_peer_state_counts") or {}
    by_window_counts = variant.get("dual_catalyst_peer_state_counts_by_window") or {}
    changed_count = int(counts.get(f"{config.marker}_changed_signal", 0))
    eligible_count = int(counts.get(f"{config.marker}_eligible_signal", 0))
    prefix = f"{config.marker}_changed_"
    tickers = sorted(
        key[len(prefix) :]
        for key, value in counts.items()
        if key.startswith(prefix)
        and key != f"{config.marker}_changed_signal"
        and int(value or 0) > 0
    )
    windows = sorted(
        label
        for label, window_counts in by_window_counts.items()
        if int(window_counts.get(f"{config.marker}_changed_signal", 0) or 0) > 0
    )
    scalar = float(variant["parameters"][config.changed_variable])
    passed = bool(
        scalar != 1.0
        and changed_count > 0
        and len(tickers) >= base.MIN_ADJUSTED_TICKERS
        and len(windows) >= base.MIN_ADJUSTED_WINDOWS
        and aggregate_delta["expected_value_score_sum"] > 0.0
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and aggregate_delta["max_drawdown_pct_max"]
        <= base.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"].get("min_survival_rate", 0.0)
        >= base.MIN_SURVIVAL_RATE
        and variant["aggregate"].get("trade_count_sum", 0)
        >= base.MIN_TRADE_COUNT
    )
    gate = {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "eligible_dual_iwm_signal_count": eligible_count,
        "changed_dual_iwm_signal_count": changed_count,
        "changed_tickers": tickers,
        "changed_windows": windows,
        "reasons": {
            "non_identity_scalar": scalar != 1.0,
            "changed_signals": changed_count,
            "adjusted_ticker_count_ok": len(tickers) >= base.MIN_ADJUSTED_TICKERS,
            "adjusted_window_count_ok": len(windows) >= base.MIN_ADJUSTED_WINDOWS,
            "aggregate_ev_delta_positive": aggregate_delta[
                "expected_value_score_sum"
            ]
            > 0.0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"]
            > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "drawdown_delta_within_limit": (
                aggregate_delta["max_drawdown_pct_max"]
                <= base.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0)
            >= base.MIN_SURVIVAL_RATE,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0)
            >= base.MIN_TRADE_COUNT,
        },
    }
    return {
        **gate,
        "eligible_dual_peer_state_signal_count": gate[
            "eligible_dual_iwm_signal_count"
        ],
        "changed_dual_peer_state_signal_count": gate[
            "changed_dual_iwm_signal_count"
        ],
        "target_peer_momentum_state": config.target_peer_state,
    }


def _metric_rows(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {label: row["metrics"] for label, row in variant["by_window"].items()}


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return base._risk_distribution(variant)


def _experiment_record(
    config: ExperimentConfig,
    payload: dict[str, Any],
) -> dict[str, Any]:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == config.decision_if_passed
    selected_scalar = best["parameters"][config.changed_variable]
    return {
        "experiment_id": config.experiment_id,
        "date": payload["completed_at"],
        "hypothesis": config.hypothesis,
        "change_type": "alpha_search",
        "changed_variable": config.changed_variable,
        "parameters": {
            "scalars_tested": list(config.scalars),
            "selected_scalar": selected_scalar,
            "target_strategy": TARGET_STRATEGY,
            "target_peer_momentum_state": config.target_peer_state,
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_dual_catalyst_trend_scalar": (
                base.ACCEPTED_DUAL_CATALYST_TREND_SCALAR
            ),
            "accepted_dual_catalyst_iwm_leader_trend_scalar": 1.0125,
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in base.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": best["aggregate"],
        "by_window_before_metrics": _metric_rows(before),
        "by_window_after_metrics": _metric_rows(best),
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
            "1_alpha_hypothesis": config.hypothesis,
            "2_prior_similar_experiments": [
                "exp-20260513-020 accepted IWM-plus-peer-leader trend risk.",
                "exp-20260515-024 accepted source-diversity peer-nonleader trend risk.",
                "exp-20260516-014 accepted dual-catalyst source-diversity trend risk.",
                "exp-20260516-015 accepted dual-catalyst IWM-leader trend risk.",
                "No prior accepted run isolated peer-state confirmation inside the accepted dual-catalyst sleeve.",
            ],
            "3_single_causal_variable": (
                f"Only {config.changed_variable} changes; Space pool, entries, "
                "exits, ranking, LLM/news, and live slots stay fixed."
            ),
            "4_success_criteria": (
                "Aggregate EV/PnL positive, at least two EV-improved windows, "
                "no EV-regressed windows, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, trade count >= 50, and changed signals cover "
                "at least two tickers and two windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_017_018_space_dual_catalyst_peer_state_risk.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None if promoted else config.rejection_reason,
        "next_evidence_needed": None if promoted else config.next_evidence_needed,
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
            "LLM soft-ranking lacks dense downstream attribution, and recent "
            "IRDM/VSAT/GSAT/ETF pool expansion failed on old_thin or drawdown. "
            "This keeps the fixed Space pool and tests one production-visible "
            "peer-state discriminator inside the accepted dual-catalyst field."
        ),
    }


def _artifact_markdown(config: ExperimentConfig, payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == config.decision_if_passed
    lines = [
        f"# {config.experiment_id} {config.stem}",
        "",
        "## Hypothesis",
        config.hypothesis,
        "",
        "## Single Changed Variable",
        f"`{config.changed_variable}` on top of accepted `{BEFORE_EXPERIMENT_ID}`.",
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- dual catalyst profile field check passed: `{payload['dual_profile_field_check']['passed']}`",
        f"- target peer state: `{config.target_peer_state}`",
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
            f"- scalar: `{best['parameters'][config.changed_variable]}`",
            f"- eligible signals: `{gate['eligible_dual_peer_state_signal_count']}`",
            f"- changed signals: `{gate['changed_dual_peer_state_signal_count']}`",
            f"- changed tickers: `{gate['changed_tickers']}`",
            f"- changed windows: `{gate['changed_windows']}`",
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


def _ticket(config: ExperimentConfig, payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    gate = payload["gate_results"]
    return {
        "experiment_id": config.experiment_id,
        "status": payload["decision"],
        "summary": (
            f"{config.changed_variable} selected {best['parameters'][config.changed_variable]} "
            f"with aggregate EV delta {gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{config.experiment_id}_{config.stem}.md"),
        "json": str(ROOT / "data" / "experiments" / config.experiment_id / f"{config.stem}.json"),
    }


def run_one(config: ExperimentConfig, gates: dict[str, Any], field_check: dict[str, Any], dual_profile_field_check: dict[str, Any]) -> dict[str, Any]:
    LOGGER.info("Running %s", config.experiment_id)
    if not field_check["passed"]:
        raise RuntimeError(f"Open-position field check failed: {field_check}")
    if not dual_profile_field_check["passed"]:
        raise RuntimeError(
            f"Dual-catalyst profile field check failed: {dual_profile_field_check}"
        )

    variants = [
        _run_variant(config, scalar=scalar, gates=gates)
        for scalar in config.scalars
    ]
    before = next(
        variant
        for variant in variants
        if float(variant["parameters"][config.changed_variable]) == 1.0
    )
    for variant in variants:
        variant["gate"] = _gate_variant(config, variant, before)
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
    decision = config.decision_if_passed if best["gate"]["passed"] else "reject"
    payload = {
        "experiment_id": config.experiment_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "gates": gates,
        "field_check": field_check,
        "dual_profile_field_check": dual_profile_field_check,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_scalar": [
            {
                "scalar": variant["parameters"][config.changed_variable],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "hypothesis": config.hypothesis,
        "changed_variable": config.changed_variable,
    }
    payload["experiment_log_record"] = _experiment_record(config, payload)
    return payload


def persist(config: ExperimentConfig, payload: dict[str, Any]) -> None:
    data_dir = ROOT / "data" / "experiments" / config.experiment_id
    _write_json(data_dir / f"{config.stem}.json", payload)
    _write_json(LOG_DIR / f"{config.experiment_id}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{config.experiment_id}.json", _ticket(config, payload))
    artifact_path = ARTIFACT_DIR / f"{config.experiment_id}_{config.stem}.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_artifact_markdown(config, payload), encoding="utf-8")
    _append_jsonl_for_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def run() -> dict[str, Any]:
    base.exp008._install_experiment_path_compat()
    gates = base.exp021._collect_gates()
    field_check = base.exp051._open_position_field_check()
    dual_profile_field_check = base.exp014._field_check_dual_catalyst_profiles()
    payloads = {}
    for config in CONFIGS:
        payload = run_one(config, gates, field_check, dual_profile_field_check)
        payloads[config.experiment_id] = payload
    return payloads


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    payloads = run()
    for config in CONFIGS:
        payload = payloads[config.experiment_id]
        persist(config, payload)
    summary = {}
    for config in CONFIGS:
        payload = payloads[config.experiment_id]
        best = payload["best_variant"]
        gate = payload["gate_results"]
        summary[config.experiment_id] = {
            "decision": payload["decision"],
            "best_scalar": best["parameters"][config.changed_variable],
            "eligible_signals": gate["eligible_dual_peer_state_signal_count"],
            "changed_signals": gate["changed_dual_peer_state_signal_count"],
            "changed_tickers": gate["changed_tickers"],
            "changed_windows": gate["changed_windows"],
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
    print(json.dumps(_safe(summary), indent=2))


if __name__ == "__main__":
    main()
