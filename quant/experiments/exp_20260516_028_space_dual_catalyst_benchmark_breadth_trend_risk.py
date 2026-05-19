"""exp-20260516-028: Space dual-catalyst benchmark-breadth trend risk.

Tests one allocation variable on top of accepted exp-20260516-024: whether
source-diverse official Space trend signals with both customer and government
catalysts deserve an incremental scalar when closed forward replacement rows
show positive 10d cash, SPY, QQQ, UFO, and ARKX relative outcomes.

The experiment keeps the Space pool, entries, exits, ranking, LLM/news
boundary, and live Space slots fixed.
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

import exp_20260516_024_space_dual_catalyst_financing_profile_trend_risk as prior


LOGGER = logging.getLogger(__name__)

# exp024 imports exp023 as `prev`; keep the accepted-stack base accessible here.
prior.base = prior.prev.base
BASE = prior.base

EXPERIMENT_ID = "exp-20260516-028"
STEM = "space_dual_catalyst_benchmark_breadth_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260516-024"
BEFORE_STEM = "space_dual_catalyst_financing_profile_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
MARKER = "space_dual_catalyst_benchmark_breadth_trend_risk"

ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR = (
    prior.ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR
)
ACCEPTED_DUAL_CATALYST_SAME_THEME_WINNER_TREND_SCALAR = (
    prior.ACCEPTED_DUAL_CATALYST_SAME_THEME_WINNER_TREND_SCALAR
)
ACCEPTED_DUAL_CATALYST_NEAR_PERFECT_TREND_SCALAR = (
    prior.ACCEPTED_DUAL_CATALYST_NEAR_PERFECT_TREND_SCALAR
)
ACCEPTED_DUAL_CATALYST_FINANCING_PROFILE_TREND_SCALAR = 1.0125
SCALARS = (0.95, 0.975, 1.0, 1.0125, 1.025, 1.05)


def _safe(value: Any) -> Any:
    return prior._safe(value)


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


def _is_benchmark_breadth_dual_signal(
    signal: dict[str, Any],
    profile: dict[str, Any] | None,
    benchmark_tickers: set[str],
) -> bool:
    ticker = str(signal.get("ticker") or "").upper()
    return (
        str(signal.get("strategy") or "") == TARGET_STRATEGY
        and ticker in benchmark_tickers
        and BASE.exp014._is_dual_catalyst_profile(profile)
    )


def _run_variant(
    *,
    benchmark_breadth_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_scale_and_record = BASE.exp041.accepted_exp._scale_and_record
    same_theme_tickers = set(
        gates["defense_budget_same_theme_winner_gate"]["target_tickers"]
    )
    same_theme_profiles = gates["defense_budget_same_theme_winner_gate"]["profiles"]
    financing_tickers = set(gates["financing_gate"]["target_tickers"])
    financing_profiles = gates["financing_gate"].get("profiles") or {}
    benchmark_tickers = set(gates["benchmark_breadth_gate"]["target_tickers"])
    benchmark_profiles = gates["benchmark_breadth_gate"].get("profiles") or {}
    near_perfect_adjustments: list[dict[str, Any]] = []
    dual_adjustments: list[dict[str, Any]] = []
    dual_iwm_adjustments: list[dict[str, Any]] = []
    dual_same_theme_adjustments: list[dict[str, Any]] = []
    dual_near_perfect_adjustments: list[dict[str, Any]] = []
    dual_financing_adjustments: list[dict[str, Any]] = []
    dual_benchmark_adjustments: list[dict[str, Any]] = []

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
            BASE.exp041.source_diversity_exp._scale_sizing(
                sizing,
                BASE.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR,
                portfolio_value,
                "space_source_diversity_peer_nonleader_trend_risk",
            )
            signal["space_source_diversity_peer_nonleader_trend_bucket"] = True
            signal["space_source_diversity_peer_nonleader_trend_scalar"] = (
                BASE.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_TREND_SCALAR
            )
            signal["space_source_diversity_peer_nonleader_profile"] = profile
        if BASE.exp044._is_target_signal(signal, profile):
            BASE.exp044._apply_extra_scale(
                signal=signal,
                sizing=sizing,
                scalar=(
                    BASE.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
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
            ] = BASE.ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_NEAR_PERFECT_TREND_SCALAR
            signal["space_source_diversity_peer_nonleader_near_perfect_profile"] = (
                profile
            )
        if not BASE.exp014._is_dual_catalyst_profile(profile):
            return
        BASE._apply_scale(
            signal=signal,
            sizing=sizing,
            scalar=BASE.ACCEPTED_DUAL_CATALYST_TREND_SCALAR,
            portfolio_value=portfolio_value,
            marker="space_dual_catalyst_source_diversity_trend_risk",
            counts=counts,
            adjustments=dual_adjustments,
            profile=profile,
        )
        signal["space_source_diversity_dual_catalyst_trend_bucket"] = True
        signal["space_source_diversity_dual_catalyst_trend_scalar"] = (
            BASE.ACCEPTED_DUAL_CATALYST_TREND_SCALAR
        )
        signal["space_source_diversity_dual_catalyst_profile"] = profile
        if str(signal.get("space_iwm_relative_state") or "") == "smallcap_leader":
            BASE._apply_scale(
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
        ticker = str(signal.get("ticker") or "").upper()
        if ticker in same_theme_tickers:
            BASE._apply_scale(
                signal=signal,
                sizing=sizing,
                scalar=ACCEPTED_DUAL_CATALYST_SAME_THEME_WINNER_TREND_SCALAR,
                portfolio_value=portfolio_value,
                marker="space_dual_catalyst_same_theme_winner_trend_risk",
                counts=counts,
                adjustments=dual_same_theme_adjustments,
                profile=same_theme_profiles.get(ticker),
            )
            signal["space_dual_catalyst_same_theme_winner_trend_bucket"] = True
            signal["space_dual_catalyst_same_theme_winner_trend_scalar"] = (
                ACCEPTED_DUAL_CATALYST_SAME_THEME_WINNER_TREND_SCALAR
            )
            signal["space_dual_catalyst_same_theme_winner_profile"] = (
                same_theme_profiles.get(ticker)
            )
        if prior.prev._is_near_perfect_dual_signal(signal, profile):
            BASE._apply_scale(
                signal=signal,
                sizing=sizing,
                scalar=ACCEPTED_DUAL_CATALYST_NEAR_PERFECT_TREND_SCALAR,
                portfolio_value=portfolio_value,
                marker="space_dual_catalyst_near_perfect_trend_risk",
                counts=counts,
                adjustments=dual_near_perfect_adjustments,
                profile=profile,
            )
            signal["space_dual_catalyst_near_perfect_trend_bucket"] = True
            signal["space_dual_catalyst_near_perfect_trend_scalar"] = (
                ACCEPTED_DUAL_CATALYST_NEAR_PERFECT_TREND_SCALAR
            )
            signal["space_dual_catalyst_near_perfect_profile"] = profile
        if prior._is_financing_dual_signal(signal, profile, financing_tickers):
            BASE._apply_scale(
                signal=signal,
                sizing=sizing,
                scalar=ACCEPTED_DUAL_CATALYST_FINANCING_PROFILE_TREND_SCALAR,
                portfolio_value=portfolio_value,
                marker="space_dual_catalyst_financing_profile_trend_risk",
                counts=counts,
                adjustments=dual_financing_adjustments,
                profile=financing_profiles.get(ticker),
            )
            signal["space_dual_catalyst_financing_profile_trend_bucket"] = True
            signal["space_dual_catalyst_financing_profile_trend_scalar"] = (
                ACCEPTED_DUAL_CATALYST_FINANCING_PROFILE_TREND_SCALAR
            )
            signal["space_dual_catalyst_financing_profile"] = (
                financing_profiles.get(ticker)
            )
        if not _is_benchmark_breadth_dual_signal(
            signal,
            profile,
            benchmark_tickers,
        ):
            return
        BASE._apply_scale(
            signal=signal,
            sizing=sizing,
            scalar=benchmark_breadth_scalar,
            portfolio_value=portfolio_value,
            marker=MARKER,
            counts=counts,
            adjustments=dual_benchmark_adjustments,
            profile=benchmark_profiles.get(ticker),
        )
        signal["space_dual_catalyst_benchmark_breadth_trend_bucket"] = True
        signal["space_dual_catalyst_benchmark_breadth_trend_scalar"] = (
            benchmark_breadth_scalar
        )
        signal["space_dual_catalyst_benchmark_breadth_profile"] = (
            benchmark_profiles.get(ticker)
        )

    BASE.exp041.accepted_exp._scale_and_record = patched_scale_and_record
    try:
        variant = BASE.exp021._run_exp051_stack_variant(
            f"{STEM}_{str(benchmark_breadth_scalar).replace('.', '_')}",
            defense_same_theme_winner_scalar=(
                BASE.ACCEPTED_DEFENSE_BUDGET_SAME_THEME_WINNER_SCALAR
            ),
            gates=gates,
        )
    finally:
        BASE.exp041.accepted_exp._scale_and_record = original_scale_and_record

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
        "accepted_dual_catalyst_iwm_leader_trend_scalar": (
            ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR
        ),
        "accepted_dual_catalyst_same_theme_winner_trend_scalar": (
            ACCEPTED_DUAL_CATALYST_SAME_THEME_WINNER_TREND_SCALAR
        ),
        "accepted_dual_catalyst_near_perfect_trend_scalar": (
            ACCEPTED_DUAL_CATALYST_NEAR_PERFECT_TREND_SCALAR
        ),
        "accepted_dual_catalyst_financing_profile_trend_scalar": (
            ACCEPTED_DUAL_CATALYST_FINANCING_PROFILE_TREND_SCALAR
        ),
        "space_dual_catalyst_benchmark_breadth_trend_scalar": (
            benchmark_breadth_scalar
        ),
        "target_strategy": TARGET_STRATEGY,
        "target_profile_gate": "benchmark_breadth_gate",
        "target_tickers": sorted(benchmark_tickers),
    }
    summarizer = BASE.exp041.source_diversity_exp._adjustment_summary
    variant["source_diversity_peer_nonleader_near_perfect_adjustment_summary"] = (
        summarizer(near_perfect_adjustments)
    )
    variant["dual_catalyst_adjustment_summary"] = summarizer(dual_adjustments)
    variant["dual_catalyst_iwm_leader_adjustment_summary"] = summarizer(
        dual_iwm_adjustments
    )
    variant["dual_catalyst_same_theme_winner_adjustment_summary"] = summarizer(
        dual_same_theme_adjustments
    )
    variant["dual_catalyst_near_perfect_adjustment_summary"] = summarizer(
        dual_near_perfect_adjustments
    )
    variant["dual_catalyst_financing_profile_adjustment_summary"] = summarizer(
        dual_financing_adjustments
    )
    variant["dual_catalyst_benchmark_breadth_counts"] = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
    }
    variant["dual_catalyst_benchmark_breadth_counts_by_window"] = by_window_counts
    variant["dual_catalyst_benchmark_breadth_adjustment_summary"] = summarizer(
        dual_benchmark_adjustments
    )
    variant["dual_catalyst_benchmark_breadth_adjustment_sample"] = (
        dual_benchmark_adjustments[:25]
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


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = BASE.exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        label: BASE.exp041.source_diversity_exp._delta(
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
    counts = variant.get("dual_catalyst_benchmark_breadth_counts") or {}
    by_window_counts = (
        variant.get("dual_catalyst_benchmark_breadth_counts_by_window") or {}
    )
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    tickers = _changed_tickers(counts)
    windows = _changed_windows(by_window_counts)
    scalar = float(
        variant["parameters"]["space_dual_catalyst_benchmark_breadth_trend_scalar"]
    )
    passed = bool(
        scalar != 1.0
        and changed_count > 0
        and len(tickers) >= BASE.MIN_ADJUSTED_TICKERS
        and len(windows) >= BASE.MIN_ADJUSTED_WINDOWS
        and aggregate_delta["expected_value_score_sum"] > 0.0
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
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "eligible_dual_benchmark_breadth_signal_count": eligible_count,
        "changed_dual_benchmark_breadth_signal_count": changed_count,
        "changed_tickers": tickers,
        "changed_windows": windows,
        "reasons": {
            "non_identity_scalar": scalar != 1.0,
            "changed_signals": changed_count,
            "adjusted_ticker_count_ok": len(tickers) >= BASE.MIN_ADJUSTED_TICKERS,
            "adjusted_window_count_ok": len(windows) >= BASE.MIN_ADJUSTED_WINDOWS,
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
                <= BASE.MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0)
            >= BASE.MIN_SURVIVAL_RATE,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0)
            >= BASE.MIN_TRADE_COUNT,
        },
    }


def _metric_rows(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {label: row["metrics"] for label, row in variant["by_window"].items()}


def _benchmark_breadth_field_check(gates: dict[str, Any]) -> dict[str, Any]:
    benchmark_gate = gates["benchmark_breadth_gate"]
    source_profiles = gates["source_diversity_gate"]["profiles"]
    benchmark_profiles = benchmark_gate.get("profiles") or {}
    benchmark_tickers = set(benchmark_gate.get("target_tickers") or [])
    target_tickers = [
        ticker
        for ticker, profile in source_profiles.items()
        if ticker in benchmark_tickers
        and BASE.exp014._is_dual_catalyst_profile(profile)
    ]
    required_profile_fields = [
        "avg_10d_cash_relative_pnl",
        "avg_10d_spy_relative_value",
        "avg_10d_qqq_relative_value",
        "avg_10d_ufo_relative_value",
        "avg_10d_arkx_relative_value",
    ]
    missing = {
        ticker: [
            field
            for field in required_profile_fields
            if benchmark_profiles.get(ticker, {}).get(field) is None
        ]
        for ticker in target_tickers
    }
    missing = {ticker: fields for ticker, fields in missing.items() if fields}
    return {
        "passed": bool(benchmark_gate.get("passed"))
        and bool(target_tickers)
        and not missing,
        "benchmark_gate_passed": bool(benchmark_gate.get("passed")),
        "required_signal_fields": [
            "strategy",
            "ticker",
            "space_source_diversity_profile.event_fields",
            *required_profile_fields,
        ],
        "target_profile_gate": "benchmark_breadth_gate",
        "target_tickers": sorted(target_tickers),
        "all_benchmark_tickers": sorted(benchmark_tickers),
        "missing_profile_fields": missing,
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    selected_scalar = best["parameters"][
        "space_dual_catalyst_benchmark_breadth_trend_scalar"
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_dual_catalyst_benchmark_breadth_trend_scalar",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": selected_scalar,
            "target_strategy": TARGET_STRATEGY,
            "target_profile_gate": "benchmark_breadth_gate",
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_dual_catalyst_iwm_leader_trend_scalar": (
                ACCEPTED_DUAL_CATALYST_IWM_LEADER_TREND_SCALAR
            ),
            "accepted_dual_catalyst_same_theme_winner_trend_scalar": (
                ACCEPTED_DUAL_CATALYST_SAME_THEME_WINNER_TREND_SCALAR
            ),
            "accepted_dual_catalyst_near_perfect_trend_scalar": (
                ACCEPTED_DUAL_CATALYST_NEAR_PERFECT_TREND_SCALAR
            ),
            "accepted_dual_catalyst_financing_profile_trend_scalar": (
                ACCEPTED_DUAL_CATALYST_FINANCING_PROFILE_TREND_SCALAR
            ),
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
            "before": BASE._risk_distribution(before),
            "after": BASE._risk_distribution(best),
        },
        "gate_answers": {
            "1_alpha_hypothesis": payload["hypothesis"],
            "2_prior_similar_experiments": [
                "exp-20260514-041 accepted broad benchmark-breadth trend risk.",
                "exp-20260516-014/015/019/023/024 accepted the current dual-catalyst Space allocation stack.",
                "exp-20260516-017/018 rejected nearby peer-state refinements with zero incremental EV/PnL.",
                "No prior run isolated benchmark-breadth replacement quality inside the accepted dual-catalyst sleeve after exp-20260516-024.",
            ],
            "3_single_causal_variable": (
                "Only the incremental dual-catalyst benchmark-breadth trend "
                "scalar changes; candidate pool, entries, exits, ranking, "
                "LLM/news, and live slots stay fixed."
            ),
            "4_success_criteria": (
                "Aggregate EV/PnL positive, at least two EV-improved windows, "
                "no EV-regressed windows, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, trade count >= 50, adjusted cohort nonzero, "
                "and changed signals cover at least two tickers and two windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_028_space_dual_catalyst_benchmark_breadth_trend_risk.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: the dual-catalyst benchmark-breadth scalar did not "
            "satisfy the fixed three-window EV/PnL, drawdown, and cohort guards."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry nearby dual-catalyst benchmark-breadth scalars on "
            "these frozen windows without new closed forward rows or a "
            "materially different production-visible replacement-quality field."
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
            "LLM soft-ranking still lacks dense downstream attribution, recent "
            "Space pool expansion was fragile, peer-state refinements produced "
            "zero incremental EV/PnL, and stronger accepted dual-catalyst "
            "scalars have drawdown sensitivity. This keeps the fixed Space "
            "pool and tests one production-visible replacement-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260516_028_space_dual_catalyst_benchmark_breadth_trend_risk.py",
            "data/experiments/exp-20260516-028/space_dual_catalyst_benchmark_breadth_trend_risk.json",
            "experiments/logs/exp-20260516-028.json",
            "experiments/tickets/exp-20260516-028.json",
            "experiments/artifacts/exp-20260516-028_space_dual_catalyst_benchmark_breadth_trend_risk.md",
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space dual-catalyst benchmark-breadth trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_dual_catalyst_benchmark_breadth_trend_scalar` on top of "
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
        f"- benchmark-breadth field check passed: `{payload['benchmark_breadth_field_check']['passed']}`",
        f"- target tickers: `{payload['benchmark_breadth_field_check'].get('target_tickers')}`",
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
            f"- scalar: `{best['parameters']['space_dual_catalyst_benchmark_breadth_trend_scalar']}`",
            f"- eligible signals: `{gate['eligible_dual_benchmark_breadth_signal_count']}`",
            f"- changed signals: `{gate['changed_dual_benchmark_breadth_signal_count']}`",
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


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Dual-catalyst benchmark-breadth Space scalar "
            f"{best['parameters']['space_dual_catalyst_benchmark_breadth_trend_scalar']} "
            f"changed {gate['changed_dual_benchmark_breadth_signal_count']} "
            "signals with aggregate EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
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
    benchmark_breadth_field_check = _benchmark_breadth_field_check(gates)
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

    variants = [
        _run_variant(benchmark_breadth_scalar=scalar, gates=gates)
        for scalar in SCALARS
    ]
    before = next(
        variant
        for variant in variants
        if float(
            variant["parameters"][
                "space_dual_catalyst_benchmark_breadth_trend_scalar"
            ]
        )
        == 1.0
    )
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
        "gates": gates,
        "field_check": field_check,
        "dual_profile_field_check": dual_profile_field_check,
        "benchmark_breadth_field_check": benchmark_breadth_field_check,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_scalar": [
            {
                "scalar": variant["parameters"][
                    "space_dual_catalyst_benchmark_breadth_trend_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "hypothesis": (
            "Accepted dual-catalyst source-diverse official Space trend "
            "signals may still be mis-sized when closed replacement rows show "
            "positive 10d outcomes versus cash, SPY, QQQ, UFO, and ARKX; "
            "this tests whether broad replacement quality strengthens that "
            "already accepted customer-plus-government catalyst stack."
        ),
        "changed_variable": "space_dual_catalyst_benchmark_breadth_trend_scalar",
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
                        "space_dual_catalyst_benchmark_breadth_trend_scalar"
                    ],
                    "eligible_signals": gate[
                        "eligible_dual_benchmark_breadth_signal_count"
                    ],
                    "changed_signals": gate[
                        "changed_dual_benchmark_breadth_signal_count"
                    ],
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
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
