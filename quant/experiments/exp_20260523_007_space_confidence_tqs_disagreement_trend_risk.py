"""exp-20260523-007: Space confidence/TQS disagreement trend risk.

Tests one allocation variable on the current accepted default-off Space stack:
whether high-TQS dual-catalyst benchmark-breadth trend signals with only
moderate signal confidence should be sized differently.

The field is production-visible in the signal payload. The experiment keeps the
Space pool, entries, exits, ranking, event gates, LLM/news boundary,
benchmark-breadth scalar, and live Space slots fixed.
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
for path in (str(ROOT), str(ROOT / "quant"), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260519_027_space_dual_catalyst_benchmark_breadth_precision_sweep as current


LOGGER = logging.getLogger(__name__)

prior = current.prior
BASE = prior.BASE

EXPERIMENT_ID = "exp-20260523-007"
STEM = "space_confidence_tqs_disagreement_trend_risk"
CURRENT_ACCEPTED_EXPERIMENT_ID = "exp-20260519-027"
CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR = 1.021875
CURRENT_ACCEPTED_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / CURRENT_ACCEPTED_EXPERIMENT_ID
    / "space_dual_catalyst_benchmark_breadth_precision_sweep.json"
)

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
TARGET_MARKER = "space_dual_catalyst_benchmark_breadth_trend_risk"
MARKER = "space_confidence_tqs_disagreement_trend_risk"
MIN_TRADE_QUALITY_SCORE = 0.95
MAX_CONFIDENCE_SCORE = 0.90
SCALARS = (0.85, 0.90, 0.95, 1.0, 1.025, 1.05, 1.075)


def _safe(value: Any) -> Any:
    return prior._safe(value)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _load_current_variant() -> dict[str, Any]:
    payload = json.loads(CURRENT_ACCEPTED_ARTIFACT.read_text(encoding="utf-8-sig"))
    if payload.get("decision") != "accept":
        raise RuntimeError(
            "Current accepted Space artifact is not accepted: "
            f"{CURRENT_ACCEPTED_ARTIFACT}"
        )
    return payload["best_variant"]


def _signal_scores(signal: dict[str, Any]) -> tuple[float | None, float | None]:
    return _safe_float(signal.get("confidence_score")), _safe_float(
        signal.get("trade_quality_score")
    )


def _is_disagreement_signal(signal: dict[str, Any]) -> bool:
    confidence, tqs = _signal_scores(signal)
    return bool(
        confidence is not None
        and tqs is not None
        and tqs >= MIN_TRADE_QUALITY_SCORE
        and confidence < MAX_CONFIDENCE_SCORE
        and tqs > confidence
    )


def _run_variant(*, disagreement_scalar: float, gates: dict[str, Any]) -> dict[str, Any]:
    original_apply_scale = BASE._apply_scale
    disagreement_adjustments: list[dict[str, Any]] = []

    def patched_apply_scale(
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
        original_apply_scale(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            marker=marker,
            counts=counts,
            adjustments=adjustments,
            profile=profile,
        )
        if marker != TARGET_MARKER:
            return
        if str(signal.get("strategy") or "") != TARGET_STRATEGY:
            return
        if not sizing:
            return

        ticker = str(signal.get("ticker") or "").upper()
        confidence, tqs = _signal_scores(signal)
        counts[f"{MARKER}_candidate_signal"] += 1
        counts[f"{MARKER}_candidate_{ticker}"] += 1
        if confidence is None:
            counts[f"{MARKER}_missing_confidence_score"] += 1
            counts[f"{MARKER}_missing_{ticker}"] += 1
            return
        if tqs is None:
            counts[f"{MARKER}_missing_trade_quality_score"] += 1
            counts[f"{MARKER}_missing_{ticker}"] += 1
            return
        if not _is_disagreement_signal(signal):
            counts[f"{MARKER}_outside_bucket_signal"] += 1
            counts[f"{MARKER}_outside_bucket_{ticker}"] += 1
            return

        original_apply_scale(
            signal=signal,
            sizing=sizing,
            scalar=disagreement_scalar,
            portfolio_value=portfolio_value,
            marker=MARKER,
            counts=counts,
            adjustments=disagreement_adjustments,
            profile=profile,
        )
        signal["space_confidence_tqs_disagreement_trend_bucket"] = True
        signal["space_confidence_tqs_disagreement_trend_scalar"] = (
            disagreement_scalar
        )
        signal["space_confidence_tqs_disagreement_confidence_score"] = confidence
        signal["space_confidence_tqs_disagreement_trade_quality_score"] = tqs

    BASE._apply_scale = patched_apply_scale
    try:
        variant = prior._run_variant(
            benchmark_breadth_scalar=CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            gates=gates,
        )
    finally:
        BASE._apply_scale = original_apply_scale

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
    summarizer = BASE.exp041.source_diversity_exp._adjustment_summary
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": CURRENT_ACCEPTED_EXPERIMENT_ID,
        "accepted_benchmark_breadth_scalar": CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR,
        "space_confidence_tqs_disagreement_trend_scalar": disagreement_scalar,
        "min_trade_quality_score": MIN_TRADE_QUALITY_SCORE,
        "max_confidence_score": MAX_CONFIDENCE_SCORE,
        "target_strategy": TARGET_STRATEGY,
        "target_marker": TARGET_MARKER,
    }
    variant["confidence_tqs_disagreement_counts"] = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
    }
    variant["confidence_tqs_disagreement_counts_by_window"] = by_window_counts
    variant["confidence_tqs_disagreement_adjustment_summary"] = summarizer(
        disagreement_adjustments
    )
    variant["confidence_tqs_disagreement_adjustment_sample"] = (
        disagreement_adjustments[:25]
    )
    return variant


def _changed_tickers(counts: dict[str, Any]) -> list[str]:
    prefix = f"{MARKER}_changed_"
    return sorted(
        key[len(prefix) :]
        for key, value in counts.items()
        if key.startswith(prefix)
        and key != f"{MARKER}_changed_signal"
        and int(value or 0) > 0
    )


def _changed_windows(by_window_counts: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(
        label
        for label, counts in by_window_counts.items()
        if int(counts.get(f"{MARKER}_changed_signal", 0) or 0) > 0
    )


def _metric_rows(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {label: row["metrics"] for label, row in variant["by_window"].items()}


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return BASE._risk_distribution(variant)


def _signal_field_check(variant: dict[str, Any]) -> dict[str, Any]:
    counts = variant.get("confidence_tqs_disagreement_counts") or {}
    candidate_count = int(counts.get(f"{MARKER}_candidate_signal", 0) or 0)
    missing_confidence = int(counts.get(f"{MARKER}_missing_confidence_score", 0) or 0)
    missing_tqs = int(counts.get(f"{MARKER}_missing_trade_quality_score", 0) or 0)
    return {
        "passed": candidate_count > 0 and missing_confidence == 0 and missing_tqs == 0,
        "required_signal_fields": [
            "ticker",
            "strategy",
            "confidence_score",
            "trade_quality_score",
            "space_dual_catalyst_benchmark_breadth_trend_bucket",
        ],
        "candidate_signal_count": candidate_count,
        "missing_confidence_score_count": missing_confidence,
        "missing_trade_quality_score_count": missing_tqs,
        "counts": counts,
    }


def _gate_variant(variant: dict[str, Any], current_variant: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = BASE.exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        current_variant["aggregate"],
    )
    by_window_delta = {
        label: BASE.exp041.source_diversity_exp._delta(
            row["metrics"],
            current_variant["by_window"][label]["metrics"],
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
    counts = variant.get("confidence_tqs_disagreement_counts") or {}
    by_window_counts = variant.get("confidence_tqs_disagreement_counts_by_window") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0) or 0)
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0) or 0)
    candidate_count = int(counts.get(f"{MARKER}_candidate_signal", 0) or 0)
    missing_confidence = int(counts.get(f"{MARKER}_missing_confidence_score", 0) or 0)
    missing_tqs = int(counts.get(f"{MARKER}_missing_trade_quality_score", 0) or 0)
    changed_tickers = _changed_tickers(counts)
    changed_windows = _changed_windows(by_window_counts)
    scalar = float(
        variant["parameters"]["space_confidence_tqs_disagreement_trend_scalar"]
    )
    required_ev_delta = float(
        current_variant["aggregate"]["expected_value_score_sum"]
    ) * 0.10
    passed = bool(
        scalar != 1.0
        and candidate_count > 0
        and missing_confidence == 0
        and missing_tqs == 0
        and changed_count > 0
        and len(changed_tickers) >= BASE.MIN_ADJUSTED_TICKERS
        and len(changed_windows) >= BASE.MIN_ADJUSTED_WINDOWS
        and aggregate_delta["expected_value_score_sum"] > required_ev_delta
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and aggregate_delta["max_drawdown_pct_max"]
        <= BASE.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"].get("min_survival_rate", 0.0)
        >= BASE.MIN_SURVIVAL_RATE
        and variant["aggregate"].get("trade_count_sum", 0)
        >= BASE.MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_current": aggregate_delta,
        "by_window_delta_vs_current": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "candidate_signal_count": candidate_count,
        "eligible_signal_count": eligible_count,
        "changed_signal_count": changed_count,
        "missing_confidence_score_count": missing_confidence,
        "missing_trade_quality_score_count": missing_tqs,
        "changed_tickers": changed_tickers,
        "changed_windows": changed_windows,
        "required_ev_delta_for_acceptance": required_ev_delta,
        "reasons": {
            "non_neutral_scalar": scalar != 1.0,
            "candidate_signals": candidate_count,
            "confidence_score_complete": missing_confidence == 0,
            "trade_quality_score_complete": missing_tqs == 0,
            "changed_signals": changed_count,
            "adjusted_ticker_count_ok": (
                len(changed_tickers) >= BASE.MIN_ADJUSTED_TICKERS
            ),
            "adjusted_window_count_ok": (
                len(changed_windows) >= BASE.MIN_ADJUSTED_WINDOWS
            ),
            "aggregate_ev_delta_above_10pct_gate": aggregate_delta[
                "expected_value_score_sum"
            ]
            > required_ev_delta,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "drawdown_delta_within_limit": (
                aggregate_delta["max_drawdown_pct_max"]
                <= BASE.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0)
            >= BASE.MIN_SURVIVAL_RATE,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0)
            >= BASE.MIN_TRADE_COUNT,
        },
    }


def _record(payload: dict[str, Any]) -> dict[str, Any]:
    current_variant = payload["current_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    selected = best["parameters"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_confidence_tqs_disagreement_trend_risk_scalar",
        "trial_family": "space_signal_quality_disagreement_allocation",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260512-008",
            "exp-20260519-027",
            "exp-20260520-020",
            "exp-20260522-019",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_signal_quality_interaction",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": selected[
                "space_confidence_tqs_disagreement_trend_scalar"
            ],
            "min_trade_quality_score": MIN_TRADE_QUALITY_SCORE,
            "max_confidence_score": MAX_CONFIDENCE_SCORE,
            "accepted_before_experiment": CURRENT_ACCEPTED_EXPERIMENT_ID,
            "accepted_benchmark_breadth_scalar": (
                CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR
            ),
            "target_strategy": TARGET_STRATEGY,
            "target_marker": TARGET_MARKER,
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in BASE.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": current_variant["aggregate"],
        "after_metrics": best["aggregate"],
        "by_window_before_metrics": _metric_rows(current_variant),
        "by_window_after_metrics": _metric_rows(best),
        "by_window_delta": gate["by_window_delta_vs_current"],
        "expected_value_score_delta": gate["aggregate_delta_vs_current"].get(
            "expected_value_score_sum"
        ),
        "total_pnl_delta": gate["aggregate_delta_vs_current"].get("total_pnl_sum"),
        "risk_distribution": {
            "before": _risk_distribution(current_variant),
            "after": _risk_distribution(best),
        },
        "gate_answers": {
            "1_alpha_hypothesis": payload["hypothesis"],
            "2_prior_similar_experiments": [
                "exp-20260512-008 accepted a broad near-perfect TQS Space trend scalar on an older stack.",
                "exp-20260519-027 accepted the current dual-catalyst benchmark-breadth precision scalar; this run does not retune that scalar.",
                "exp-20260520-020 rejected a short-extension signal-quality scalar because it only helped one window.",
                "exp-20260522-019 rejected forward-consistency because current support was only one LUNR signal.",
            ],
            "3_single_causal_variable": (
                "Only one extra scalar changes for benchmark-breadth Space "
                "trend signals where trade_quality_score is high but "
                "confidence_score remains below 0.90. Pool, entry, exit, "
                "ranking, LLM/news, catalyst profiles, benchmark-breadth scalar, "
                "and live slots remain fixed."
            ),
            "4_success_criteria": (
                "Because this is another Space allocation scalar, aggregate EV "
                "delta must exceed 10% of current Space aggregate EV, aggregate "
                "PnL must improve, at least two windows must improve, no window "
                "may regress, drawdown drift <= 0.5 pp, survival >= 5%, trade "
                "count >= 50, fields complete, and adjusted cohort spans at "
                "least two tickers and two windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260523_007_space_confidence_tqs_disagreement_trend_risk.py"
            ),
        },
        "gate_results": gate,
        "gate_results_by_variant": payload["gate_results_by_variant"],
        "field_checks": {
            "open_position": payload["field_check"],
            "dual_profile": payload["dual_profile_field_check"],
            "benchmark_breadth": payload["benchmark_breadth_field_check"],
            "signal": payload["signal_field_check"],
        },
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: no confidence/TQS disagreement scalar cleared the "
            "strict 10% EV, multi-window, no-regression, cohort breadth, "
            "drawdown, survival, and trade-count acceptance gates."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry this confidence/TQS disagreement scalar on the frozen "
            "Space sample. Next Space alpha should move toward capped activation "
            "or displacement evidence after more closed forward observations."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "Accepted scalar must be promoted through shared "
                "space_catalyst_sleeve.py metadata/policy and parity tests; "
                "live Space slots remain zero until separate promotion."
                if promoted
                else "Experiment-only wrapper; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking is still underpowered; Space pool pruning and VSAT "
            "satcom additions were rejected; short-extension and forward "
            "consistency were recently rejected. This uses an existing "
            "production-visible signal-quality interaction instead."
        ),
        "related_files": [
            "quant/experiments/exp_20260523_007_space_confidence_tqs_disagreement_trend_risk.py",
            "data/experiments/exp-20260523-007/space_confidence_tqs_disagreement_trend_risk.json",
            "experiments/logs/exp-20260523-007.json",
            "experiments/tickets/exp-20260523-007.json",
            "experiments/artifacts/exp-20260523-007_space_confidence_tqs_disagreement_trend_risk.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    current_variant = payload["current_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space confidence/TQS disagreement trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        "`space_confidence_tqs_disagreement_trend_risk_scalar` gated by high TQS and moderate confidence.",
        "",
        "## Gate 1 Baseline",
        f"- current accepted experiment: `{CURRENT_ACCEPTED_EXPERIMENT_ID}`",
        f"- current benchmark-breadth scalar: `{CURRENT_ACCEPTED_BENCHMARK_BREADTH_SCALAR}`",
        f"- current aggregate EV: `{current_variant['aggregate']['expected_value_score_sum']}`",
        f"- current aggregate PnL: `{current_variant['aggregate']['total_pnl_sum']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- dual catalyst profile field check passed: `{payload['dual_profile_field_check']['passed']}`",
        f"- benchmark-breadth field check passed: `{payload['benchmark_breadth_field_check']['passed']}`",
        f"- signal field check passed: `{payload['signal_field_check']['passed']}`",
        f"- candidate signals: `{payload['signal_field_check']['candidate_signal_count']}`",
        f"- missing confidence_score: `{payload['signal_field_check']['missing_confidence_score_count']}`",
        f"- missing trade_quality_score: `{payload['signal_field_check']['missing_trade_quality_score_count']}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{current_variant['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no filter was added; this is a sizing-only scalar.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_current"].items():
        before_metrics = current_variant["by_window"][label]["metrics"]
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
    selected = best["parameters"]
    lines.extend(
        [
            "",
            "## Best Variant",
            f"- scalar: `{selected['space_confidence_tqs_disagreement_trend_scalar']}`",
            f"- candidate signals: `{gate['candidate_signal_count']}`",
            f"- eligible signals: `{gate['eligible_signal_count']}`",
            f"- changed signals: `{gate['changed_signal_count']}`",
            f"- changed tickers: `{gate['changed_tickers']}`",
            f"- changed windows: `{gate['changed_windows']}`",
            f"- required EV delta for acceptance: `{gate['required_ev_delta_for_acceptance']}`",
            f"- aggregate EV delta vs current: `{gate['aggregate_delta_vs_current']['expected_value_score_sum']}`",
            f"- aggregate PnL delta vs current: `{gate['aggregate_delta_vs_current']['total_pnl_sum']}`",
            f"- max drawdown delta vs current: `{gate['aggregate_delta_vs_current']['max_drawdown_pct_max']}`",
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
    selected = best["parameters"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Space confidence/TQS disagreement scalar "
            f"{selected['space_confidence_tqs_disagreement_trend_scalar']} "
            f"changed {gate['changed_signal_count']} signals with EV delta "
            f"{gate['aggregate_delta_vs_current']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    BASE.exp008._install_experiment_path_compat()
    gates = BASE.exp021._collect_gates()
    field_check = BASE.exp051._open_position_field_check()
    dual_profile_field_check = BASE.exp014._field_check_dual_catalyst_profiles()
    benchmark_breadth_field_check = prior._benchmark_breadth_field_check(gates)
    if not field_check["passed"]:
        raise RuntimeError(f"Open-position field check failed: {field_check}")
    if not dual_profile_field_check["passed"]:
        raise RuntimeError(
            f"Dual-catalyst profile field check failed: {dual_profile_field_check}"
        )
    if not benchmark_breadth_field_check["passed"]:
        raise RuntimeError(
            "Benchmark-breadth profile field check failed: "
            f"{benchmark_breadth_field_check}"
        )

    current_variant = _load_current_variant()
    variants = [
        _run_variant(disagreement_scalar=scalar, gates=gates)
        for scalar in SCALARS
    ]
    signal_field_check = _signal_field_check(variants[0])
    if not signal_field_check["passed"]:
        raise RuntimeError(
            f"Confidence/TQS signal field check failed: {signal_field_check}"
        )
    for variant in variants:
        variant["gate"] = _gate_variant(variant, current_variant)

    accepted = [variant for variant in variants if variant["gate"]["passed"]]
    best = max(
        accepted or variants,
        key=lambda item: (
            item["gate"]["aggregate_delta_vs_current"]["expected_value_score_sum"],
            item["gate"]["aggregate_delta_vs_current"]["total_pnl_sum"],
        ),
    )
    decision = "accept" if best["gate"]["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "gates": gates,
        "field_check": field_check,
        "dual_profile_field_check": dual_profile_field_check,
        "benchmark_breadth_field_check": benchmark_breadth_field_check,
        "signal_field_check": signal_field_check,
        "current_variant": current_variant,
        "variants": variants,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_variant": [
            {
                "scalar": variant["parameters"][
                    "space_confidence_tqs_disagreement_trend_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "hypothesis": (
            "Within accepted dual-catalyst benchmark-breadth Space trend "
            "signals, high trade_quality_score with only moderate "
            "confidence_score may identify a catalyst/price-action setup that "
            "the generic signal confidence underweights. A bounded scalar on "
            "that disagreement bucket could improve EV without changing the "
            "candidate pool, LLM/news boundary, or live Space slots."
        ),
        "changed_variable": "space_confidence_tqs_disagreement_trend_risk_scalar",
    }
    payload["experiment_log_record"] = _record(payload)
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
    selected = best["parameters"]
    gate = payload["gate_results"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_scalar": selected[
                        "space_confidence_tqs_disagreement_trend_scalar"
                    ],
                    "candidate_signals": gate["candidate_signal_count"],
                    "eligible_signals": gate["eligible_signal_count"],
                    "changed_signals": gate["changed_signal_count"],
                    "changed_tickers": gate["changed_tickers"],
                    "changed_windows": gate["changed_windows"],
                    "required_ev_delta_for_acceptance": gate[
                        "required_ev_delta_for_acceptance"
                    ],
                    "aggregate_ev_delta_vs_current": gate[
                        "aggregate_delta_vs_current"
                    ]["expected_value_score_sum"],
                    "aggregate_pnl_delta_vs_current": gate[
                        "aggregate_delta_vs_current"
                    ]["total_pnl_sum"],
                    "max_drawdown_delta_vs_current": gate[
                        "aggregate_delta_vs_current"
                    ]["max_drawdown_pct_max"],
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
