"""exp-20260515-005: Space benchmark-breadth peer-leader breakout risk.

Tests one risk-allocation variable on top of the accepted exp-20260514-053
default-off Space stack: whether official Space breakout signals whose closed
10d event-state profile beats cash, SPY, QQQ, UFO, and ARKX should get a
different risk scalar only when the ticker is also a Space peer-momentum
leader.

This keeps the candidate pool, entries, exits, ranking, LLM authority, and live
Space slots fixed.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT / "quant"), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import portfolio_engine  # noqa: E402
import exp_20260514_041_space_benchmark_breadth_trend_risk as exp041  # noqa: E402
import exp_20260514_051_space_defense_budget_delayed_benchmark_trend_risk as exp051  # noqa: E402
import exp_20260514_053_space_benchmark_breadth_iwm_leader_trend_risk as exp053  # noqa: E402


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260515-005"
STEM = "space_benchmark_breadth_peer_leader_breakout_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-053"
BEFORE_STEM = "space_benchmark_breadth_iwm_leader_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "breakout_long"
TARGET_PEER_STATE = "leader"
MARKER = "space_benchmark_breadth_peer_leader_breakout_risk"

ACCEPTED_IWM_LEADER_SCALAR = 1.0125
SCALARS = (1.0, 0.0, 0.25, 0.5, 0.75, 1.0125, 1.025, 1.05, 1.075, 1.1)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


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
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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


def _window_label(window: dict[str, Any]) -> str:
    for label, spec in exp041.source_diversity_exp.WINDOWS.items():
        if (
            str(window.get("start")) == str(spec.get("start"))
            and str(window.get("end")) == str(spec.get("end"))
        ):
            return label
    return "unknown"


def _scale_and_record(
    *,
    signal: dict[str, Any],
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    marker: str,
    counts: Counter[str],
    counts_by_window: defaultdict[str, Counter[str]],
    window_label: str,
    adjustments: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> None:
    ticker = str(signal.get("ticker") or "").upper()
    shares_before = int(sizing.get("shares_to_buy") or 0)
    dollars_before = float(sizing.get("position_size_dollars") or 0.0)
    exp041.source_diversity_exp._scale_sizing(
        sizing,
        scalar,
        portfolio_value,
        marker,
    )
    shares_after = int(sizing.get("shares_to_buy") or 0)
    dollars_after = float(sizing.get("position_size_dollars") or 0.0)
    for bucket in (counts, counts_by_window[window_label]):
        bucket[f"{marker}_eligible_signal"] += 1
        bucket[f"{marker}_eligible_{ticker}"] += 1
        if shares_after != shares_before:
            bucket[f"{marker}_changed_signal"] += 1
            bucket[f"{marker}_changed_{ticker}"] += 1
    adjustments.append(
        {
            "ticker": ticker,
            "strategy": signal.get("strategy"),
            "window": window_label,
            "marker": marker,
            "scalar": scalar,
            "shares_before_scalar": shares_before,
            "shares_after_scalar": shares_after,
            "dollars_before_scalar": dollars_before,
            "dollars_after_scalar": dollars_after,
            "profile": profile,
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
    )


def _run_exp053_stack_variant(
    label: str,
    *,
    breakout_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_size = portfolio_engine.size_signals
    original_run_window = exp041.source_diversity_exp._run_window
    current_window = {"label": "unknown"}
    benchmark_tickers = set(gates["benchmark_breadth_gate"]["target_tickers"])
    benchmark_profiles = gates["benchmark_breadth_gate"]["profiles"]
    adjustments: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    counts_by_window: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def wrapped_run_window(
        window: dict[str, Any],
        universe: list[str],
        snapshot_key: str,
    ) -> dict[str, Any]:
        previous = current_window["label"]
        current_window["label"] = _window_label(window)
        try:
            return original_run_window(window, universe, snapshot_key)
        finally:
            current_window["label"] = previous

    def wrapped_size_signals(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original_size(signals, portfolio_value, risk_pct=risk_pct)
        out: list[dict[str, Any]] = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            sizing = deepcopy(signal.get("sizing") or {})
            peer_state = str(signal.get("space_peer_momentum_state") or "")
            if (
                ticker in benchmark_tickers
                and strategy == TARGET_STRATEGY
                and peer_state == TARGET_PEER_STATE
                and sizing
            ):
                _scale_and_record(
                    signal=signal,
                    sizing=sizing,
                    scalar=breakout_scalar,
                    portfolio_value=portfolio_value,
                    marker=MARKER,
                    counts=counts,
                    counts_by_window=counts_by_window,
                    window_label=current_window["label"],
                    adjustments=adjustments,
                    profile=benchmark_profiles.get(ticker),
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_benchmark_breadth_peer_leader_breakout_bucket": True,
                    "space_benchmark_breadth_peer_leader_breakout_scalar": (
                        breakout_scalar
                    ),
                    "space_benchmark_breadth_profile": benchmark_profiles.get(ticker),
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = wrapped_size_signals
    exp041.source_diversity_exp._run_window = wrapped_run_window
    try:
        variant = exp053._run_exp051_stack_variant(
            label,
            iwm_leader_scalar=ACCEPTED_IWM_LEADER_SCALAR,
            gates=gates,
        )
    finally:
        exp041.source_diversity_exp._run_window = original_run_window
        portfolio_engine.size_signals = original_size

    counts_by_window_serialized = {
        name: dict(sorted(bucket.items()))
        for name, bucket in sorted(counts_by_window.items())
    }
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "accepted_benchmark_breadth_iwm_leader_trend_scalar": (
            ACCEPTED_IWM_LEADER_SCALAR
        ),
        "space_benchmark_breadth_peer_leader_breakout_scalar": breakout_scalar,
        "target_strategy": TARGET_STRATEGY,
        "target_peer_momentum_state": TARGET_PEER_STATE,
        "benchmark_breadth_target_tickers": sorted(benchmark_tickers),
    }
    variant["benchmark_breadth_peer_leader_breakout_counts"] = dict(
        sorted(counts.items())
    )
    variant["benchmark_breadth_peer_leader_breakout_counts_by_window"] = (
        counts_by_window_serialized
    )
    variant["benchmark_breadth_peer_leader_breakout_adjustment_summary"] = (
        exp041.source_diversity_exp._adjustment_summary(adjustments)
    )
    variant["benchmark_breadth_peer_leader_breakout_adjustment_sample"] = (
        adjustments[:25]
    )
    for window_name, row in variant["by_window"].items():
        row["benchmark_breadth_peer_leader_breakout_counts"] = (
            counts_by_window_serialized.get(window_name, {})
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
    improved_windows = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] > 1e-9
    }
    regressed_windows = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] < -1e-9
    }
    counts = variant.get("benchmark_breadth_peer_leader_breakout_counts") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    scalar = float(
        variant["parameters"][
            "space_benchmark_breadth_peer_leader_breakout_scalar"
        ]
    )
    passed = bool(
        scalar != 1.0
        and changed_count > 0
        and aggregate_delta["expected_value_score_sum"] > 0.0
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(improved_windows) >= 2
        and not regressed_windows
        and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and variant["aggregate"].get("min_survival_rate", 0.0) >= MIN_SURVIVAL_RATE
        and variant["aggregate"].get("trade_count_sum", 0) >= MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "eligible_breakout_signal_count": eligible_count,
        "changed_breakout_signal_count": changed_count,
        "reasons": {
            "non_identity_scalar": scalar != 1.0,
            "changed_signals": changed_count,
            "aggregate_ev_delta_positive": (
                aggregate_delta["expected_value_score_sum"] > 0.0
            ),
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(improved_windows) >= 2,
            "no_window_regressed": not regressed_windows,
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


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    decision = payload["decision"]
    promoted = decision == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": (
            "Official Space breakout signals with broad closed 10d benchmark "
            "confirmation may need a different risk allocation only when "
            "same-theme peer momentum confirms leadership."
        ),
        "change_type": "alpha_search",
        "changed_variable": "space_benchmark_breadth_peer_leader_breakout_scalar",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": best["parameters"][
                "space_benchmark_breadth_peer_leader_breakout_scalar"
            ],
            "target_strategy": TARGET_STRATEGY,
            "target_peer_momentum_state": TARGET_PEER_STATE,
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_benchmark_breadth_iwm_leader_trend_scalar": (
                ACCEPTED_IWM_LEADER_SCALAR
            ),
            "benchmark_breadth_target_tickers": payload["gates"][
                "benchmark_breadth_gate"
            ]["target_tickers"],
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
            "before": {
                label: {
                    key: row["metrics"].get(key)
                    for key in (
                        "worst_trade_pct",
                        "max_consecutive_losses",
                        "tail_loss_share",
                    )
                }
                for label, row in before["by_window"].items()
            },
            "after": {
                label: {
                    key: row["metrics"].get(key)
                    for key in (
                        "worst_trade_pct",
                        "max_consecutive_losses",
                        "tail_loss_share",
                    )
                }
                for label, row in best["by_window"].items()
            },
        },
        "gate_results": gate,
        "decision": decision,
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: selected scalar did not improve enough fixed "
            "windows without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "A materially different breakout-quality field, or new closed "
            "Space forward rows that separate breakout continuation from "
            "fragile event beta."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promoted,
            "replay_only": True,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "Accepted helper should be promoted to shared "
                "space_catalyst_sleeve.py metadata/risk-scalar path; live Space "
                "slots remain zero."
                if promoted
                else "Experiment-only monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited; GSAT/VSAT/IRDM broad "
            "candidate expansion and recent benchmark-breadth peer/source "
            "scalar retunes were rejected or already accepted. This keeps the "
            "candidate set fixed and tests one production-visible closed "
            "event-state variable in the remaining breakout pocket."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    best = payload["best_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space benchmark-breadth peer-leader breakout risk",
        "",
        "## Hypothesis",
        (
            "Official Space `breakout_long` signals with broad 10d confirmation "
            "versus cash, SPY, QQQ, UFO, and ARKX may need different sizing only "
            "when the ticker is also a Space peer-momentum leader."
        ),
        "",
        "## Single Changed Variable",
        (
            "`space_benchmark_breadth_peer_leader_breakout_scalar` on top of the accepted "
            f"`{BEFORE_EXPERIMENT_ID}` Space stack."
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
        f"- benchmark-breadth gate passed: `{payload['gates']['benchmark_breadth_gate']['passed']}`",
        f"- benchmark-breadth target tickers: `{payload['gates']['benchmark_breadth_gate']['target_tickers']}`",
        f"- target strategy: `{TARGET_STRATEGY}`",
        f"- target peer momentum state: `{TARGET_PEER_STATE}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no entry filter was added; only sizing changes.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = best["by_window"][label]["metrics"]
        adjusted = best[
            "benchmark_breadth_peer_leader_breakout_counts_by_window"
        ].get(
            label,
            {},
        ).get(f"{MARKER}_changed_signal", 0)
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} | {adjusted} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
                adjusted=adjusted,
            )
        )
    lines.extend(
        [
            "",
            "## Best Variant",
            f"- scalar: `{best['parameters']['space_benchmark_breadth_peer_leader_breakout_scalar']}`",
            f"- eligible signals: `{gate['eligible_breakout_signal_count']}`",
            f"- adjusted signals: `{gate['changed_breakout_signal_count']}`",
            f"- adjusted counts: `{best['benchmark_breadth_peer_leader_breakout_counts']}`",
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
            "  backtester_adapter_changed: false",
            f"  run_adapter_changed: {str(promoted).lower()}",
            "  replay_only: true",
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
            f"Benchmark-breadth peer-leader breakout scalar "
            f"{best['parameters']['space_benchmark_breadth_peer_leader_breakout_scalar']} "
            f"changed {gate['changed_breakout_signal_count']} signals with "
            f"aggregate EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    core = exp041.source_diversity_exp._run_core_baseline()
    gates = exp051._collect_gates()
    variants = [
        _run_exp053_stack_variant(
            label=f"{STEM}_{str(scalar).replace('.', '_')}",
            breakout_scalar=scalar,
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
                item["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    field_check = exp051._open_position_field_check()
    decision = "accept" if best["gate"]["passed"] and field_check["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "core_baseline": core,
        "gates": gates,
        "field_check": field_check,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best["gate"],
        "gate_results_by_scalar": [
            {
                "scalar": variant["parameters"][
                    "space_benchmark_breadth_peer_leader_breakout_scalar"
                ],
                **variant["gate"],
            }
            for variant in variants
        ],
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "alpha_hypothesis": (
            "Benchmark-breadth Space breakout signals may need a distinct "
            "risk allocation only when peer momentum confirms leadership."
        ),
        "changed_variable": "space_benchmark_breadth_peer_leader_breakout_scalar",
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
                        "space_benchmark_breadth_peer_leader_breakout_scalar"
                    ],
                    "eligible_signals": gate["eligible_breakout_signal_count"],
                    "adjusted_signals": gate["changed_breakout_signal_count"],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
