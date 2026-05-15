"""exp-20260515-047: Space source-diversity launch/lunar trend risk.

Tests one allocation variable on top of the accepted exp-20260515-044 Space
stack: whether source-diverse official Space trend signals in the production
universe-registry launch/lunar segment deserve a separate default-off risk
scalar.

This keeps the Space candidate pool fixed and avoids LLM soft-ranking,
candidate admission, entry/exit changes, ranking changes, and live Space slots.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260514_041_space_benchmark_breadth_trend_risk as exp041
import exp_20260514_051_space_defense_budget_delayed_benchmark_trend_risk as exp051
import exp_20260515_021_space_defense_budget_same_theme_winner_trend_risk as exp021
import exp_20260515_044_space_source_diversity_peer_nonleader_near_perfect_trend_risk as exp044


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260515-047"
STEM = "space_source_diversity_launch_lunar_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260515-044"
BEFORE_STEM = "space_source_diversity_peer_nonleader_near_perfect_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
TARGET_THEME_SEGMENT = "launch_lunar"
MARKER = "space_source_diversity_launch_lunar_trend_risk"

ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR = 1.05
ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR = 1.025
ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR = 1.025
SCALARS = (1.0, 0.75, 0.9, 0.975, 1.0125, 1.025, 1.05, 1.075)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50

SPACE_THEME_SEGMENTS = {
    "ASTS": "satellite_connectivity",
    "BKSY": "space_data_defense",
    "LUNR": "launch_lunar",
    "PL": "space_data_defense",
    "RDW": "space_data_defense",
    "RKLB": "launch_lunar",
}


def _safe(value: Any) -> Any:
    return exp051._safe(value)


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


def _theme_segment_for_ticker(ticker: str) -> str | None:
    return SPACE_THEME_SEGMENTS.get(str(ticker or "").upper())


def _field_check_theme_segments() -> dict[str, Any]:
    path = ROOT / "data" / "universe_registry.json"
    if not path.exists():
        return {"passed": False, "path": str(path), "missing": "file"}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("tickers") or {}
    official_tickers = sorted(exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)
    segments: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    mismatched: list[str] = []
    for ticker in official_tickers:
        record = records.get(ticker) or {}
        expected = _theme_segment_for_ticker(ticker)
        actual = record.get("theme_segment")
        segments[ticker] = {
            "expected": expected,
            "actual": actual,
            "status": record.get("status"),
            "pilot_sleeve": record.get("pilot_sleeve"),
            "liquidity_tier": record.get("liquidity_tier"),
        }
        if not actual:
            missing.append(ticker)
        if expected != actual:
            mismatched.append(ticker)
    target_tickers = sorted(
        ticker
        for ticker in official_tickers
        if _theme_segment_for_ticker(ticker) == TARGET_THEME_SEGMENT
    )
    return {
        "passed": not missing and not mismatched and bool(target_tickers),
        "path": str(path.relative_to(ROOT)),
        "target_theme_segment": TARGET_THEME_SEGMENT,
        "target_tickers": target_tickers,
        "segments": segments,
        "missing_theme_segment": missing,
        "mismatched_theme_segment": mismatched,
    }


def _apply_launch_lunar_scale(
    *,
    signal: dict[str, Any],
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    counts: Counter[str],
    adjustments: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    theme_segment: str | None,
) -> None:
    ticker = str(signal.get("ticker") or "").upper()
    shares_before = int(sizing.get("shares_to_buy") or 0)
    dollars_before = float(sizing.get("position_size_dollars") or 0.0)
    exp041.source_diversity_exp._scale_sizing(
        sizing,
        scalar,
        portfolio_value,
        MARKER,
    )
    shares_after = int(sizing.get("shares_to_buy") or 0)
    dollars_after = float(sizing.get("position_size_dollars") or 0.0)
    counts[f"{MARKER}_eligible_signal"] += 1
    counts[f"{MARKER}_eligible_{ticker}"] += 1
    if shares_after != shares_before:
        counts[f"{MARKER}_changed_signal"] += 1
        counts[f"{MARKER}_changed_{ticker}"] += 1
    adjustments.append(
        {
            "ticker": ticker,
            "strategy": signal.get("strategy"),
            "date": str(signal.get("date") or ""),
            "marker": MARKER,
            "scalar": scalar,
            "shares_before_scalar": shares_before,
            "shares_after_scalar": shares_after,
            "dollars_before_scalar": dollars_before,
            "dollars_after_scalar": dollars_after,
            "theme_segment": theme_segment,
            "source_diversity_profile": profile,
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_peer_excess_momentum_20d_pct": signal.get(
                "space_peer_excess_momentum_20d_pct"
            ),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
    )


def _run_current_stack_variant(
    label: str,
    *,
    launch_lunar_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_scale_and_record = exp041.accepted_exp._scale_and_record
    near_perfect_adjustments: list[dict[str, Any]] = []
    launch_lunar_adjustments: list[dict[str, Any]] = []

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
            exp041.source_diversity_exp._scale_sizing(
                sizing,
                ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR,
                portfolio_value,
                "space_source_diversity_peer_nonleader_trend_risk",
            )
            signal["space_source_diversity_peer_nonleader_trend_bucket"] = True
            signal["space_source_diversity_peer_nonleader_trend_scalar"] = (
                ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR
            )
            signal["space_source_diversity_peer_nonleader_profile"] = profile
        if exp044._is_target_signal(signal, profile):
            exp044._apply_extra_scale(
                signal=signal,
                sizing=sizing,
                scalar=(
                    ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
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
            ] = ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
            signal[
                "space_source_diversity_peer_nonleader_near_perfect_profile"
            ] = profile

        ticker = str(signal.get("ticker") or "").upper()
        theme_segment = signal.get("space_theme_segment") or _theme_segment_for_ticker(
            ticker
        )
        if theme_segment != TARGET_THEME_SEGMENT:
            return
        _apply_launch_lunar_scale(
            signal=signal,
            sizing=sizing,
            scalar=launch_lunar_scalar,
            portfolio_value=portfolio_value,
            counts=counts,
            adjustments=launch_lunar_adjustments,
            profile=profile,
            theme_segment=str(theme_segment),
        )
        signal["space_source_diversity_launch_lunar_trend_bucket"] = True
        signal["space_source_diversity_launch_lunar_trend_scalar"] = (
            launch_lunar_scalar
        )
        signal["space_source_diversity_launch_lunar_profile"] = profile
        signal["space_source_diversity_launch_lunar_theme_segment"] = theme_segment

    exp041.accepted_exp._scale_and_record = patched_scale_and_record
    try:
        variant = exp021._run_exp051_stack_variant(
            label,
            defense_same_theme_winner_scalar=(
                ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR
            ),
            gates=gates,
        )
    finally:
        exp041.accepted_exp._scale_and_record = original_scale_and_record

    counts = Counter(variant.get("source_diversity_trend_counts") or {})
    by_window_counts = {
        name: {
            key: value
            for key, value in sorted(
                (row.get("source_diversity_trend_counts") or {}).items()
            )
            if MARKER in key
        }
        for name, row in variant["by_window"].items()
    }
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "accepted_defense_budget_same_theme_winner_trend_scalar": (
            ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR
        ),
        "accepted_source_diversity_peer_nonleader_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR
        ),
        "accepted_source_diversity_peer_nonleader_near_perfect_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
        ),
        "space_source_diversity_launch_lunar_trend_scalar": (
            launch_lunar_scalar
        ),
        "target_strategy": TARGET_STRATEGY,
        "target_theme_segment": TARGET_THEME_SEGMENT,
        "target_tickers": sorted(
            ticker
            for ticker, segment in SPACE_THEME_SEGMENTS.items()
            if segment == TARGET_THEME_SEGMENT
        ),
    }
    variant["source_diversity_peer_nonleader_near_perfect_adjustment_summary"] = (
        exp041.source_diversity_exp._adjustment_summary(near_perfect_adjustments)
    )
    variant["source_diversity_launch_lunar_counts"] = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
    }
    variant["source_diversity_launch_lunar_counts_by_window"] = by_window_counts
    variant["source_diversity_launch_lunar_adjustment_summary"] = (
        exp041.source_diversity_exp._adjustment_summary(launch_lunar_adjustments)
    )
    variant["source_diversity_launch_lunar_adjustment_sample"] = (
        launch_lunar_adjustments[:25]
    )
    return variant


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        label: exp041.source_diversity_exp._delta(
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
    counts = variant.get("source_diversity_launch_lunar_counts") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    scalar = float(
        variant["parameters"]["space_source_diversity_launch_lunar_trend_scalar"]
    )
    passed = bool(
        scalar != 1.0
        and changed_count > 0
        and aggregate_delta["expected_value_score_sum"] > 0.0
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"].get("min_survival_rate", 0.0) >= MIN_SURVIVAL_RATE
        and variant["aggregate"].get("trade_count_sum", 0) >= MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "eligible_launch_lunar_signal_count": eligible_count,
        "changed_launch_lunar_signal_count": changed_count,
        "reasons": {
            "non_identity_scalar": scalar != 1.0,
            "changed_signals": changed_count,
            "aggregate_ev_delta_positive": aggregate_delta[
                "expected_value_score_sum"
            ]
            > 0.0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "drawdown_delta_within_limit": (
                aggregate_delta["max_drawdown_pct_max"]
                <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0)
            >= MIN_SURVIVAL_RATE,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0)
            >= MIN_TRADE_COUNT,
        },
    }


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
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": (
            "Source-diverse official Space trend signals in the launch/lunar "
            "theme segment may be mis-sized by the accepted default-off Space stack."
        ),
        "change_type": "alpha_search",
        "changed_variable": "space_source_diversity_launch_lunar_trend_scalar",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": best["parameters"][
                "space_source_diversity_launch_lunar_trend_scalar"
            ],
            "target_strategy": TARGET_STRATEGY,
            "target_theme_segment": TARGET_THEME_SEGMENT,
            "target_tickers": best["parameters"]["target_tickers"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_source_diversity_peer_nonleader_trend_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR
            ),
            "accepted_source_diversity_peer_nonleader_near_perfect_trend_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
            ),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec for label, spec in exp041.source_diversity_exp.WINDOWS.items()
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
                "Risk allocation: source-diverse Space trend signals with "
                "theme_segment=launch_lunar may deserve a distinct scalar."
            ),
            "2_prior_similar_experiments": [
                "exp-20260512-032 accepted broad launch/lunar theme-segment risk on an older Space stack.",
                "exp-20260515-019 rejected theme-beta ETF pool expansion.",
                "exp-20260515-021 accepted defense-budget same-theme winner trend risk.",
                "exp-20260515-024 accepted source-diversity peer-nonleader trend risk.",
                "exp-20260515-044 accepted near-perfect TQS inside source-diversity peer-nonleader trend.",
                "exp-20260515-045 rejected company-release source-diversity trend scalar.",
                "No prior current-stack run isolated launch/lunar source-diversity trend profiles on top of exp-20260515-044.",
            ],
            "3_single_causal_variable": (
                "Only the launch/lunar source-diversity trend scalar changes."
            ),
            "4_success_criteria": (
                "Aggregate EV/PnL positive, at least two EV-improved windows, "
                "no EV-regressed windows, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, trade count >= 50, and adjusted cohort nonzero."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260515_047_space_source_diversity_launch_lunar_trend_risk.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: the launch/lunar source-diversity trend scalar did "
            "not improve the fixed windows while satisfying PnL and drawdown "
            "guardrails."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry nearby launch/lunar source-diversity trend scalars on "
            "these frozen windows without new closed forward rows or a different "
            "production-visible catalyst-quality field."
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
            "LLM soft-ranking remains attribution-limited and recent Space "
            "ticker/ETF admissions regressed cross-window evidence. This run "
            "keeps the fixed pool and tests a registry-backed catalyst segment."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space source-diversity launch/lunar trend risk",
        "",
        "## Hypothesis",
        (
            "Source-diverse official Space `trend_long` signals may need a "
            "different default-off allocation when the ticker belongs to the "
            "production universe-registry `launch_lunar` theme segment."
        ),
        "",
        "## Single Changed Variable",
        (
            "`space_source_diversity_launch_lunar_trend_scalar` on top of "
            f"accepted `{BEFORE_EXPERIMENT_ID}`."
        ),
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- theme segment field check passed: `{payload['theme_segment_field_check']['passed']}`",
        f"- target segment: `{TARGET_THEME_SEGMENT}`",
        f"- target tickers: `{best['parameters']['target_tickers']}`",
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
            f"- scalar: `{best['parameters']['space_source_diversity_launch_lunar_trend_scalar']}`",
            f"- eligible signals: `{gate['eligible_launch_lunar_signal_count']}`",
            f"- adjusted signals: `{gate['changed_launch_lunar_signal_count']}`",
            f"- adjusted counts: `{best['source_diversity_launch_lunar_counts']}`",
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
            "Launch/lunar source-diversity trend scalar "
            f"{best['parameters']['space_source_diversity_launch_lunar_trend_scalar']} "
            f"changed {gate['changed_launch_lunar_signal_count']} signals with "
            "aggregate EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    core = exp041.source_diversity_exp._run_core_baseline()
    gates = exp021._collect_gates()
    field_check = exp051._open_position_field_check()
    theme_segment_field_check = _field_check_theme_segments()
    if not field_check["passed"]:
        raise RuntimeError(f"Open-position field check failed: {field_check}")
    if not theme_segment_field_check["passed"]:
        raise RuntimeError(
            f"Theme-segment field check failed: {theme_segment_field_check}"
        )

    variants = [
        _run_current_stack_variant(
            label=f"{STEM}_{str(scalar).replace('.', '_')}",
            launch_lunar_scalar=scalar,
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
        "theme_segment_field_check": theme_segment_field_check,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_scalar": [
            {
                "scalar": variant["parameters"][
                    "space_source_diversity_launch_lunar_trend_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "alpha_hypothesis": (
            "Source-diverse Space trend signals in the launch/lunar theme "
            "segment may be mis-sized in the accepted stack."
        ),
        "changed_variable": "space_source_diversity_launch_lunar_trend_scalar",
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
                        "space_source_diversity_launch_lunar_trend_scalar"
                    ],
                    "eligible_signals": gate["eligible_launch_lunar_signal_count"],
                    "adjusted_signals": gate["changed_launch_lunar_signal_count"],
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
