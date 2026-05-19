"""exp-20260514-051: Space defense-budget delayed benchmark trend risk.

This experiment keeps the accepted exp-20260514-047 Space stack intact and tests
one new risk-allocation variable: a small trend-risk top-up for official Space
tickers whose closed defense-budget/government-contract event state shows weak
5d cash absorption but broad positive 10d benchmark confirmation.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

import exp_20260514_041_space_benchmark_breadth_trend_risk as exp041
import exp_20260514_047_space_benchmark_same_theme_strength_trend_risk as exp047

LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260514-051"
STEM = "space_defense_budget_delayed_benchmark_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-047"
BEFORE_STEM = "space_benchmark_breadth_same_theme_strength_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

LEDGER_PATH = ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
OPEN_POSITIONS_PATH = ROOT / "operator_inputs" / "open_positions.json"

TARGET_STRATEGY = "trend_long"
TARGET_SEMANTIC_BUCKET = "defense_budget_theme"
TARGET_EVENT_FIELD = "government_space_contract"
MARKER = "space_defense_budget_delayed_benchmark_trend_risk"

ACCEPTED_SAME_THEME_STRENGTH_SCALAR = 1.025
MAX_AVG_5D_CASH_RELATIVE_PNL = 0.0
MIN_AVG_10D_RELATIVE_PNL = 0.0
MIN_TARGET_PROFILE_ROWS = 2
SCALARS = (1.0, 1.025, 1.05, 1.075, 1.10)


def _safe(value: Any) -> Any:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return round(value, 6)
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _event_fields(row: dict[str, Any]) -> set[str]:
    fields = row.get("event_fields")
    if isinstance(fields, str):
        return {fields}
    if isinstance(fields, list):
        return {str(item) for item in fields if item is not None}
    if isinstance(fields, dict):
        return {str(key) for key, value in fields.items() if value}
    return set()


def _horizon(row: dict[str, Any], days: int, key: str) -> float | None:
    horizon = exp041._horizon(row, f"{days}d")
    if horizon is None:
        return None
    return _as_float(horizon.get(key))


def _is_official_space_ticker(ticker: str) -> bool:
    return ticker.upper() in exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS


def _defense_budget_delayed_benchmark_gate() -> dict[str, Any]:
    """Return target tickers with weak 5d absorption and broad 10d confirmation."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exp041._latest_closed_rows(LEDGER_PATH):
        ticker = str(row.get("ticker") or "").upper()
        if not ticker or not _is_official_space_ticker(ticker):
            continue
        if row.get("semantic_bucket") != TARGET_SEMANTIC_BUCKET:
            continue
        if TARGET_EVENT_FIELD not in _event_fields(row):
            continue
        if _horizon(row, 5, "cash_relative_pnl") is None:
            continue
        required_10d = {
            "cash_relative_pnl": _horizon(row, 10, "cash_relative_pnl"),
            "spy_relative_value": _horizon(row, 10, "spy_relative_value"),
            "qqq_relative_value": _horizon(row, 10, "qqq_relative_value"),
            "ufo_relative_value": _horizon(row, 10, "ufo_relative_value"),
            "arkx_relative_value": _horizon(row, 10, "arkx_relative_value"),
        }
        if any(value is None for value in required_10d.values()):
            continue
        grouped[ticker].append(row)

    profiles: dict[str, dict[str, Any]] = {}
    target_tickers: list[str] = []
    target_profile_row_count = 0
    for ticker, rows in sorted(grouped.items()):
        avg_5d_cash = _avg([value for row in rows if (value := _horizon(row, 5, "cash_relative_pnl")) is not None])
        avg_10d_cash = _avg([value for row in rows if (value := _horizon(row, 10, "cash_relative_pnl")) is not None])
        avg_10d_spy = _avg([value for row in rows if (value := _horizon(row, 10, "spy_relative_value")) is not None])
        avg_10d_qqq = _avg([value for row in rows if (value := _horizon(row, 10, "qqq_relative_value")) is not None])
        avg_10d_ufo = _avg([value for row in rows if (value := _horizon(row, 10, "ufo_relative_value")) is not None])
        avg_10d_arkx = _avg([value for row in rows if (value := _horizon(row, 10, "arkx_relative_value")) is not None])
        passed = (
            avg_5d_cash is not None
            and avg_5d_cash <= MAX_AVG_5D_CASH_RELATIVE_PNL
            and avg_10d_cash is not None
            and avg_10d_cash > MIN_AVG_10D_RELATIVE_PNL
            and avg_10d_spy is not None
            and avg_10d_spy > MIN_AVG_10D_RELATIVE_PNL
            and avg_10d_qqq is not None
            and avg_10d_qqq > MIN_AVG_10D_RELATIVE_PNL
            and avg_10d_ufo is not None
            and avg_10d_ufo > MIN_AVG_10D_RELATIVE_PNL
            and avg_10d_arkx is not None
            and avg_10d_arkx > MIN_AVG_10D_RELATIVE_PNL
        )
        profile = {
            "ticker": ticker,
            "row_count": len(rows),
            "avg_5d_cash_relative_pnl": avg_5d_cash,
            "avg_10d_cash_relative_pnl": avg_10d_cash,
            "avg_10d_spy_relative_pnl": avg_10d_spy,
            "avg_10d_qqq_relative_pnl": avg_10d_qqq,
            "avg_10d_ufo_relative_pnl": avg_10d_ufo,
            "avg_10d_arkx_relative_pnl": avg_10d_arkx,
            "passed": passed,
        }
        profiles[ticker] = profile
        if passed:
            target_tickers.append(ticker)
            target_profile_row_count += len(rows)

    return {
        "target_tickers": target_tickers,
        "profiles": profiles,
        "target_profile_row_count": target_profile_row_count,
        "passed": target_profile_row_count >= MIN_TARGET_PROFILE_ROWS,
        "criteria": {
            "semantic_bucket": TARGET_SEMANTIC_BUCKET,
            "event_field": TARGET_EVENT_FIELD,
            "max_avg_5d_cash_relative_pnl": MAX_AVG_5D_CASH_RELATIVE_PNL,
            "min_avg_10d_relative_pnl": MIN_AVG_10D_RELATIVE_PNL,
            "min_target_profile_rows": MIN_TARGET_PROFILE_ROWS,
        },
    }


def _extra_scale_and_record(
    *,
    signal: dict[str, Any],
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    counts: Counter[str],
    adjustments: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> None:
    ticker = str(signal.get("ticker") or "").upper()
    shares_before = int(sizing.get("shares_to_buy") or 0)
    dollars_before = float(sizing.get("position_size_dollars") or 0.0)
    exp041.source_diversity_exp._scale_sizing(sizing, scalar, portfolio_value, MARKER)
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
            "profile": profile,
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
    )


def _run_exp047_stack_variant(label: str, defense_budget_scalar: float, gates: dict[str, Any]) -> dict[str, Any]:
    original_extra = exp041._scale_and_record_extra
    target_tickers = set(gates["defense_budget_delayed_benchmark_gate"]["target_tickers"])
    profiles = gates["defense_budget_delayed_benchmark_gate"]["profiles"]
    extra_adjustments: list[dict[str, Any]] = []

    def patched_extra(
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
        original_extra(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            marker=marker,
            counts=counts,
            adjustments=adjustments,
            profile=profile,
        )
        if marker != "space_benchmark_breadth_trend_risk":
            return
        if str(signal.get("strategy") or "") != TARGET_STRATEGY:
            return
        if not sizing:
            return
        ticker = str(signal.get("ticker") or "").upper()
        if ticker not in target_tickers:
            return
        _extra_scale_and_record(
            signal=signal,
            sizing=sizing,
            scalar=defense_budget_scalar,
            portfolio_value=portfolio_value,
            counts=counts,
            adjustments=extra_adjustments,
            profile=profiles.get(ticker),
        )
        signal["space_defense_budget_delayed_benchmark_trend_bucket"] = True
        signal["space_defense_budget_delayed_benchmark_trend_scalar"] = defense_budget_scalar
        signal["space_defense_budget_delayed_benchmark_profile"] = profiles.get(ticker)

    exp041._scale_and_record_extra = patched_extra
    try:
        variant = exp047._run_exp044_stack_variant(
            label=label,
            same_theme_strength_scalar=ACCEPTED_SAME_THEME_STRENGTH_SCALAR,
            gates=gates,
        )
    finally:
        exp041._scale_and_record_extra = original_extra

    variant["defense_budget_delayed_benchmark_scalar"] = defense_budget_scalar
    counts = Counter(variant.get("source_diversity_trend_counts") or {})
    variant["defense_budget_delayed_benchmark_counts"] = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
    }
    variant["defense_budget_delayed_benchmark_adjusted_signal_count"] = counts.get(
        f"{MARKER}_changed_signal",
        0,
    )
    variant["defense_budget_delayed_benchmark_eligible_signal_count"] = counts.get(
        f"{MARKER}_eligible_signal",
        0,
    )
    variant["defense_budget_delayed_benchmark_sample_signals"] = extra_adjustments[:12]
    variant["defense_budget_delayed_benchmark_target_tickers"] = sorted(target_tickers)
    return variant


def _gate_variant(
    *,
    variant: dict[str, Any],
    before: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, Any]:
    deltas = exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window = {
        label: exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in variant["by_window"].items()
    }
    improved_windows = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window.items()
        if metrics["expected_value_score"] > 1e-9
    }
    regressed_windows = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window.items()
        if metrics["expected_value_score"] < -1e-9
    }
    counts = variant.get("defense_budget_delayed_benchmark_counts") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    sample_guard_passed = (
        gates["defense_budget_delayed_benchmark_gate"]["target_profile_row_count"] >= MIN_TARGET_PROFILE_ROWS
        and changed_count > 0
    )
    passed = (
        variant["defense_budget_delayed_benchmark_scalar"] != 1.0
        and sample_guard_passed
        and deltas["expected_value_score_sum"] > 0.0
        and deltas["total_pnl_sum"] > 0.0
        and len(improved_windows) >= 2
        and not regressed_windows
        and deltas["max_drawdown_pct_max"] <= 0.005
        and variant["aggregate"].get("min_survival_rate", 0.0) >= 0.05
        and variant["aggregate"].get("trade_count_sum", 0) >= 50
    )
    return {
        "aggregate_delta_vs_before": deltas,
        "by_window_delta_vs_before": by_window,
        "passed": passed,
        "sample_guard_passed": sample_guard_passed,
        "improved_windows": improved_windows,
        "regressed_windows": regressed_windows,
        "eligible_defense_budget_delayed_benchmark_signal_count": eligible_count,
        "changed_defense_budget_delayed_benchmark_signal_count": changed_count,
        "reasons": {
            "non_identity_scalar": variant["defense_budget_delayed_benchmark_scalar"] != 1.0,
            "profile_rows": gates["defense_budget_delayed_benchmark_gate"]["target_profile_row_count"],
            "eligible_signals": eligible_count,
            "changed_signals": changed_count,
            "aggregate_ev_delta_positive": deltas["expected_value_score_sum"] > 0.0,
            "aggregate_pnl_delta_positive": deltas["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(improved_windows) >= 2,
            "no_window_regressed": not regressed_windows,
            "drawdown_delta_within_limit": deltas["max_drawdown_pct_max"] <= 0.005,
            "survival_rate_ok": variant["aggregate"].get("min_survival_rate", 0.0) >= 0.05,
            "trade_count_ok": variant["aggregate"].get("trade_count_sum", 0) >= 50,
        },
    }


def _collect_gates() -> dict[str, Any]:
    gates = exp047._collect_gates()
    gates["defense_budget_delayed_benchmark_gate"] = _defense_budget_delayed_benchmark_gate()
    return gates


def _open_position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_PATH.exists():
        return {"path": str(OPEN_POSITIONS_PATH), "exists": False, "passed": False}
    payload = json.loads(OPEN_POSITIONS_PATH.read_text(encoding="utf-8"))
    positions = payload.get("positions", payload)
    if isinstance(positions, dict):
        positions = list(positions.values())
    if not isinstance(positions, list):
        positions = []
    missing_entry = 0
    missing_target = 0
    for position in positions:
        if not isinstance(position, dict):
            continue
        if position.get("entry_date") in (None, ""):
            missing_entry += 1
        if position.get("target_price") in (None, ""):
            missing_target += 1
    return {
        "path": str(OPEN_POSITIONS_PATH),
        "exists": True,
        "position_count": len(positions),
        "missing_entry_date": missing_entry,
        "missing_target_price": missing_target,
        "passed": missing_entry == 0 and missing_target == 0,
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    before = payload["before_variant"]
    gates = payload["gates"]
    decision = payload["decision"]
    selected_scalar = best["defense_budget_delayed_benchmark_scalar"]
    best_gate = payload["gate_results"]
    promoted = decision == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": (
            "Official Space trend signals tied to defense-budget/government-contract catalysts with weak 5d "
            "absorption but broad positive 10d benchmark confirmation deserve a small risk top-up."
        ),
        "change_type": "alpha_search",
        "changed_variable": "space_defense_budget_delayed_benchmark_trend_risk_scalar",
        "parameters": {
            "scalars_tested": list(SCALARS),
            "selected_scalar": selected_scalar,
            "strategy": TARGET_STRATEGY,
            "semantic_bucket": TARGET_SEMANTIC_BUCKET,
            "event_field": TARGET_EVENT_FIELD,
            "max_avg_5d_cash_relative_pnl": MAX_AVG_5D_CASH_RELATIVE_PNL,
            "min_avg_10d_relative_pnl": MIN_AVG_10D_RELATIVE_PNL,
            "accepted_same_theme_strength_scalar": ACCEPTED_SAME_THEME_STRENGTH_SCALAR,
            "target_tickers": gates["defense_budget_delayed_benchmark_gate"]["target_tickers"],
            "target_profile_row_count": gates["defense_budget_delayed_benchmark_gate"]["target_profile_row_count"],
        },
        "backtest_protocol": "docs/backtesting.md fixed 3-window Space protocol using frozen Space augmented snapshots",
        "date_range": {
            label: spec for label, spec in exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": best["aggregate"],
        "by_window_before_metrics": {label: item["metrics"] for label, item in before["by_window"].items()},
        "by_window_after_metrics": {label: item["metrics"] for label, item in best["by_window"].items()},
        "by_window_delta": best_gate["by_window_delta_vs_before"],
        "expected_value_score_delta": best_gate["aggregate_delta_vs_before"].get("expected_value_score_sum"),
        "total_pnl_delta": best_gate["aggregate_delta_vs_before"].get("total_pnl_sum"),
        "risk_distribution": {
            "before": before.get("risk_distribution", {}),
            "after": best.get("risk_distribution", {}),
            "delta": best_gate["aggregate_delta_vs_before"],
        },
        "gate_results": payload["gate_results"],
        "decision": decision,
        "rejection_reason": None
        if decision == "accept"
        else "Gate 4 failed: selected scalar did not improve EV/PnL across enough windows without regression.",
        "next_evidence_needed": None
        if decision == "accept"
        else "More closed defense-budget catalyst rows or a materially different production-visible timing feature.",
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promoted,
            "replay_only": True,
            "parity_test_added": promoted,
            "notes": (
                "Accepted helper promoted to shared space_catalyst_sleeve.py "
                "metadata/risk-scalar path; live Space slots remain zero."
                if promoted
                else "Experiment-only monkey patch on accepted Space stack; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited; previous scalar retunes around source diversity, same-theme "
            "strength, and customer-win timing were rejected or already accepted. This run tests one new "
            "catalyst-timing interaction only."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    before = payload["before_variant"]
    gates = payload["gates"]
    gate_results = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} {STEM}",
        "",
        "## Hypothesis",
        "",
        (
            "Official Space `trend_long` signals tied to `defense_budget_theme` / "
            "`government_space_contract` catalysts may be under-sized when 5d cash absorption is weak "
            "but 10d cash, SPY, QQQ, UFO, and ARKX relative outcomes are all positive."
        ),
        "",
        "## Single Changed Variable",
        "",
        "`space_defense_budget_delayed_benchmark_trend_risk_scalar` on top of the accepted "
        f"`{BEFORE_EXPERIMENT_ID}` Space stack.",
        "",
        "## Gate 1 Baseline",
        "",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        f"- aggregate before max drawdown pct max: `{before['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        "",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- Space catalyst profile gate passed: `{gates['defense_budget_delayed_benchmark_gate']['passed']}`",
        f"- target tickers: `{gates['defense_budget_delayed_benchmark_gate']['target_tickers']}`",
        f"- target profile rows: `{gates['defense_budget_delayed_benchmark_gate']['target_profile_row_count']}`",
        "",
        "## Gate 3 Survival Audit",
        "",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{best['aggregate']['min_survival_rate']}`",
        "- no filter was added; trade count and survival should not decline except through sizing-side effects.",
        "",
        "## Gate 4 Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate_results["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = best["by_window"][label]["metrics"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {trades_before} | {trades_after} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                trades_before=before_metrics.get("trade_count", before_metrics.get("trades", "")),
                trades_after=after_metrics.get("trade_count", after_metrics.get("trades", "")),
            )
        )
    lines.extend(
        [
            "",
            "## Best Variant",
            "",
            f"- scalar: `{best['defense_budget_delayed_benchmark_scalar']}`",
            f"- adjusted signals: `{best['defense_budget_delayed_benchmark_adjusted_signal_count']}`",
            f"- adjusted counts: `{best['defense_budget_delayed_benchmark_counts']}`",
            f"- aggregate EV delta: `{gate_results['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate_results['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- max drawdown pct max delta: `{gate_results['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
            "",
            "## Decision",
            "",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate_results['passed']}`",
            f"- improved windows: `{gate_results['improved_windows']}`",
            f"- regressed windows: `{gate_results['regressed_windows']}`",
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(promoted).lower()}",
            "  backtester_adapter_changed: false",
            f"  run_adapter_changed: {str(promoted).lower()}",
            "  replay_only: true",
            f"  parity_test_added: {str(promoted).lower()}",
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
            f"Defense-budget delayed benchmark trend risk scalar {best['defense_budget_delayed_benchmark_scalar']} "
            f"changed {best['defense_budget_delayed_benchmark_adjusted_signal_count']} signals with aggregate EV "
            f"delta {gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    core = exp041.source_diversity_exp._run_core_baseline()
    gates = _collect_gates()
    variants = [
        _run_exp047_stack_variant(
            label=f"{STEM}_{str(scalar).replace('.', '_')}",
            defense_budget_scalar=scalar,
            gates=gates,
        )
        for scalar in SCALARS
    ]
    before = variants[0]
    for variant in variants:
        variant["gate"] = _gate_variant(variant=variant, before=before, gates=gates)
    gate_results_by_scalar = [
        {
            "scalar": variant["defense_budget_delayed_benchmark_scalar"],
            **variant["gate"],
        }
        for variant in variants
    ]
    accepted_variants = [variant for variant in variants if variant["gate"]["passed"]]
    if accepted_variants:
        best = max(
            accepted_variants,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"].get("expected_value_score_sum", 0.0),
                item["gate"]["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
            ),
        )
    else:
        best = max(
            variants,
            key=lambda item: (
                item["gate"]["aggregate_delta_vs_before"].get("expected_value_score_sum", 0.0),
                item["gate"]["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
            ),
        )
    best_gate = best["gate"]
    field_check = _open_position_field_check()
    decision = "accept" if best_gate["passed"] and field_check["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "core_baseline": core,
        "gates": gates,
        "field_check": field_check,
        "variants": variants,
        "before_variant": before,
        "best_variant": best,
        "gate_results": best_gate,
        "gate_results_by_scalar": gate_results_by_scalar,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "alpha_hypothesis": (
            "Defense-budget/government-contract Space trend signals with weak 5d absorption and broad positive "
            "10d benchmark confirmation deserve a small risk top-up."
        ),
        "changed_variable": "space_defense_budget_delayed_benchmark_trend_risk_scalar",
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
                    "best_scalar": best["defense_budget_delayed_benchmark_scalar"],
                    "adjusted_signals": best["defense_budget_delayed_benchmark_adjusted_signal_count"],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"]["expected_value_score_sum"],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"]["total_pnl_sum"],
                    "target_tickers": payload["gates"]["defense_budget_delayed_benchmark_gate"]["target_tickers"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
