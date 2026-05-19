"""exp-20260513-002: Space customer-win pool scope.

Tests one candidate-pool variable on top of the accepted exp-20260512-112
default-off Space stack: keep only official Space tickers with direct
``customer_win`` event-seed coverage from accepted official/customer source
types. This is a pool-quality test, not a scalar retune or LLM ranking test.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exp_20260511_115_space_basket_momentum_risk import (  # noqa: E402
    OFFICIAL_SPACE_TICKERS,
    PROJECT_ROOT,
    WINDOWS,
    _adjustment_summary,
    _aggregate,
    _aggregate_delta,
    _delta,
    _gate2_open_positions,
    _metrics,
    _restore_policy,
    _run_core_baseline,
    _run_window,
    _safe,
    _space_trade_attribution,
    _write_json,
)
from exp_20260512_038_space_official_customer_source_risk import (  # noqa: E402
    _event_seed_profiles,
)
from exp_20260512_041_space_financing_dilution_profile_risk import (  # noqa: E402
    _field_check_event_guard_profiles as _accepted_financing_profile_gate,
)
from exp_20260512_110_space_company_release_source_risk import (  # noqa: E402
    ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    _field_check_company_release_source,
)
from exp_20260512_112_space_watch_liquidity_risk import (  # noqa: E402
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    WATCH_LIQUIDITY_RISK_SCALARS,
    _field_check_watch_liquidity_tier,
    _install_space_policy,
)
from data_layer import get_universe  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260513-002"
STEM = "space_customer_win_pool_scope"
ACCEPTED_WATCH_LIQUIDITY_RISK_SCALAR = 1.10
TARGET_EVENT_FIELD = "customer_win"


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _customer_win_pool_gate(source_gate: dict[str, Any]) -> dict[str, Any]:
    profiles = source_gate.get("profiles") or {}
    target_tickers = sorted(
        ticker
        for ticker, profile in profiles.items()
        if TARGET_EVENT_FIELD in set(profile.get("event_fields") or [])
        and ticker in OFFICIAL_SPACE_TICKERS
    )
    excluded = sorted(set(OFFICIAL_SPACE_TICKERS) - set(target_tickers))
    return {
        "passed": bool(target_tickers) and not source_gate.get("missing_required_fields"),
        "target_event_field": TARGET_EVENT_FIELD,
        "target_tickers": target_tickers,
        "excluded_official_space_tickers": excluded,
        "profiles": {ticker: profiles[ticker] for ticker in target_tickers},
        "source_gate_path": source_gate.get("path"),
    }


def _run_pool_variant(
    name: str,
    included_space_tickers: list[str],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
    source_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(included_space_tickers) | {"IWM", "SPY"})
    (
        original_generate,
        original_enrich,
        original_size,
        watch_adjustments,
        watch_counts,
        company_release_adjustments,
        company_release_counts,
        financing_adjustments,
        financing_counts,
        source_adjustments,
        source_counts,
        liquidity_ok_adjustments,
        theme_adjustments,
        iwm_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        theme_counts,
        iwm_state_counts,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_space_policy(
        ACCEPTED_WATCH_LIQUIDITY_RISK_SCALAR,
        liquidity_gate,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_watch = len(watch_adjustments)
            before_company = len(company_release_adjustments)
            before_financing = len(financing_adjustments)
            before_source = len(source_adjustments)
            before_liquidity_ok = len(liquidity_ok_adjustments)
            before_theme = len(theme_adjustments)
            before_iwm = len(iwm_adjustments)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_watch_liquidity_tier_adjustment": _adjustment_summary(
                    watch_adjustments[before_watch:]
                ),
                "space_company_release_source_adjustment": _adjustment_summary(
                    company_release_adjustments[before_company:]
                ),
                "space_financing_dilution_profile_adjustment": _adjustment_summary(
                    financing_adjustments[before_financing:]
                ),
                "space_official_customer_source_adjustment": _adjustment_summary(
                    source_adjustments[before_source:]
                ),
                "space_liquidity_tier_adjustment": _adjustment_summary(
                    liquidity_ok_adjustments[before_liquidity_ok:]
                ),
                "space_launch_lunar_theme_adjustment": _adjustment_summary(
                    theme_adjustments[before_theme:]
                ),
                "space_iwm_relative_momentum_adjustment": _adjustment_summary(
                    iwm_adjustments[before_iwm:]
                ),
                "space_peer_nonleader_breakout_adjustment": _adjustment_summary(
                    peer_nonleader_breakout_adjustments[before_peer:]
                ),
                "space_near_perfect_tqs_trend_adjustment": _adjustment_summary(
                    near_perfect_adjustments[before_near:]
                ),
                "space_perfect_tqs_risk_adjustment": _adjustment_summary(
                    perfect_adjustments[before_perfect:]
                ),
                "space_basket_positive_adjustment": _adjustment_summary(
                    basket_adjustments[before_basket:]
                ),
                "space_watch_liquidity_tier_signal_counts": dict(
                    sorted(watch_counts.items())
                ),
                "space_company_release_source_signal_counts": dict(
                    sorted(company_release_counts.items())
                ),
                "space_financing_dilution_profile_signal_counts": dict(
                    sorted(financing_counts.items())
                ),
                "space_source_eligible_signal_counts": dict(sorted(source_counts.items())),
                "space_theme_segment_signal_counts": dict(sorted(theme_counts.items())),
                "space_iwm_relative_state_counts": dict(sorted(iwm_state_counts.items())),
                "space_peer_momentum_state_counts": dict(sorted(peer_counts.items())),
                "space_near_perfect_tqs_trend_signal_counts": dict(
                    sorted(near_perfect_counts.items())
                ),
                "space_perfect_tqs_signal_counts": dict(sorted(perfect_counts.items())),
                "space_basket_signal_state_counts": dict(sorted(basket_counts.items())),
                "space_iwm_relative_day_counts": dict(sorted(day_counts.items())),
            }
    finally:
        _restore_policy(original_generate, original_enrich, original_size)
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "included_space_tickers": list(included_space_tickers),
        "excluded_official_space_tickers": sorted(
            set(OFFICIAL_SPACE_TICKERS) - set(included_space_tickers)
        ),
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _gate(after: dict[str, Any], before: dict[str, Any], core: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(after["aggregate"], before["aggregate"])
    aggregate_delta_vs_core = _aggregate_delta(after["aggregate"], core["aggregate"])
    by_window_delta = {
        label: _delta(row["metrics"], before["by_window"][label]["metrics"])
        for label, row in after["by_window"].items()
    }
    windows_ev_improved = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) > 0
    )
    windows_ev_regressed = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) < 0
    )
    removed_trade_count = -min(0, aggregate_delta.get("trade_count_sum", 0))
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= 0.005
        and after["aggregate"]["min_survival_rate"] >= 0.05
        and after["aggregate"]["trade_count_sum"] >= 50
        and removed_trade_count > 0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "removed_trade_count": removed_trade_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Space customer-win pool scope",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: restrict official Space pool membership to tickers "
            "with direct `customer_win` event-seed coverage."
        ),
        (
            f"- Aggregate EV delta vs accepted: "
            f"`{payload['expected_value_score_delta']:+.4f}`"
        ),
        (
            "- Aggregate PnL delta vs accepted: "
            f"`${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`"
        ),
        (
            "- Included tickers: "
            f"`{', '.join(payload['parameters']['included_space_tickers'])}`"
        ),
        (
            "- Excluded tickers: "
            f"`{', '.join(payload['parameters']['excluded_official_space_tickers'])}`"
        ),
        "",
        "## Three-Window Comparison",
        "",
        (
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
            "dPnL | Trades | Max DD | Survival |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} |".format(
                label=label,
                before_ev=before["expected_value_score"],
                after_ev=after["expected_value_score"],
                delta_ev=delta.get("expected_value_score", 0),
                before_pnl=before["total_pnl"],
                after_pnl=after["total_pnl"],
                delta_pnl=delta.get("total_pnl", 0),
                trades=after["trade_count"],
                max_dd=after["max_drawdown_pct"],
                survival=after["survival_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Field Check",
            "",
            json.dumps(payload["gate2"]["customer_win_pool"], sort_keys=True),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], sort_keys=True),
            "",
        ]
    )
    return "\n".join(lines)


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    gate2_open = _gate2_open_positions()
    if not gate2_open["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_open}")
    source_gate = _event_seed_profiles()
    if not source_gate["passed"]:
        raise RuntimeError(f"Accepted event source field check failed: {source_gate}")
    financing_gate = _accepted_financing_profile_gate()
    if not financing_gate["passed"]:
        raise RuntimeError(f"Accepted financing profile field check failed: {financing_gate}")
    company_release_gate = _field_check_company_release_source()
    if not company_release_gate["passed"]:
        raise RuntimeError(
            f"Accepted company-release source field check failed: {company_release_gate}"
        )
    liquidity_gate = _field_check_watch_liquidity_tier()
    if not liquidity_gate["passed"]:
        raise RuntimeError(f"Accepted watch-liquidity field check failed: {liquidity_gate}")
    customer_pool_gate = _customer_win_pool_gate(source_gate)
    if not customer_pool_gate["passed"]:
        raise RuntimeError(f"Customer-win pool field check failed: {customer_pool_gate}")

    core = _run_core_baseline()
    before = _run_pool_variant(
        "accepted_exp112_all_official_space_pool",
        list(OFFICIAL_SPACE_TICKERS),
        liquidity_gate,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    after = _run_pool_variant(
        "customer_win_official_space_pool",
        customer_pool_gate["target_tickers"],
        liquidity_gate,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    gate4 = _gate(after, before, core)
    accepted = gate4["passed"]
    decision = (
        "accepted_default_off_space_customer_win_pool_scope"
        if accepted
        else "rejected_space_customer_win_pool_scope"
    )
    interpretation = (
        "Restricting the default-off Space pool to direct customer-win official-source "
        "tickers improved the accepted Space stack under the three-window gate. "
        "Promotion must remain shared metadata-only with live Space slots at zero."
        if accepted
        else (
            "Restricting the default-off Space pool to direct customer-win tickers did "
            "not beat the accepted exp-20260512-112 all-official operating pool. "
            "The evidence supports keeping non-customer official Space tickers in the "
            "observe-only pool and allocating risk by quality fields instead of "
            "pruning the pool."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "candidate_pool_scope",
        "changed_variable": "space_customer_win_pool_membership",
        "single_causal_variable": (
            "official Space candidate pool membership restricted to tickers with "
            "direct customer_win event-seed coverage"
        ),
        "hypothesis": (
            "Customer-win source scalars improved the Space sleeve, so a cleaner "
            "candidate pool containing only direct customer-win official-source "
            "tickers may improve replacement value versus the broader official "
            "operating pool without adding noisy tickers, LLM ranking, or new "
            "risk scalars."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate-pool quality: restrict default-off Space membership "
                "to direct customer-win official-source tickers."
            ),
            "2_history_check": {
                "exp-20260512-038": (
                    "Accepted broad official customer-source 1.10x scalar; this "
                    "tests whether that evidence should become a pool-scope rule."
                ),
                "exp-20260512-110": (
                    "Accepted company-release customer-source scalar for RKLB; fixed "
                    "inside the before stack."
                ),
                "exp-20260512-112": (
                    "Accepted watch-liquidity scalar; this is the fixed before state."
                ),
                "rejected_nearby_pool_work": (
                    "GSAT/mature-satcom noisy expansions were rejected. This run "
                    "prunes by official customer-win coverage instead of adding "
                    "more tickers."
                ),
            },
            "3_single_causal_variable": (
                "space_customer_win_pool_membership. Accepted risk scalars, targets, "
                "stops, ranking, add-ons, LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, >=50 total trades, "
                "and actual trade removal."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
            "quant\\experiments\\exp_20260513_002_space_customer_win_pool_scope.py"
            ),
        },
        "parameters": {
            "accepted_before_experiment": "exp-20260512-112",
            "official_space_tickers_before": list(OFFICIAL_SPACE_TICKERS),
            "included_space_tickers": customer_pool_gate["target_tickers"],
            "excluded_official_space_tickers": customer_pool_gate[
                "excluded_official_space_tickers"
            ],
            "target_event_field": TARGET_EVENT_FIELD,
            "accepted_watch_liquidity_risk_scalar": (
                ACCEPTED_WATCH_LIQUIDITY_RISK_SCALAR
            ),
            "accepted_watch_liquidity_tested_scalars": list(
                WATCH_LIQUIDITY_RISK_SCALARS
            ),
            "accepted_company_release_source_risk_scalar": (
                ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR
            ),
            "accepted_financing_dilution_profile_risk_scalar": (
                ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR
            ),
            "locked_variables": [
                "accepted Space base risk scalar",
                "accepted basket-positive scalar",
                "accepted perfect-TQS scalar",
                "accepted near-perfect trend TQS scalar",
                "accepted peer-nonleader breakout scalar",
                "accepted IWM-relative small-cap scalar",
                "accepted launch/lunar scalar",
                "accepted liquidity_tier=ok scalar",
                "accepted watch-liquidity scalar",
                "accepted official customer-source scalar",
                "accepted company-release customer-source scalar",
                "accepted financing/dilution profile scalar",
                "accepted Space trend targets",
                "core production universe",
                "core signal generation",
                "entry filters",
                "ranking",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["space_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses canonical "
            "snapshots; Space variants use exp-20260510-028 augmented Space snapshots. "
            "The accepted_before variant reproduces exp-20260512-112 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. This experiment changes only "
                "the default-off research pool scope and does not create live slots."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "accepted_official_customer_source_profile": source_gate,
            "accepted_financing_dilution_profiles": financing_gate,
            "accepted_company_release_source_profile": company_release_gate,
            "accepted_watch_liquidity_tier_registry": liquidity_gate,
            "customer_win_pool": customer_pool_gate,
            "passed": (
                gate2_open["passed"]
                and source_gate["passed"]
                and financing_gate["passed"]
                and company_release_gate["passed"]
                and liquidity_gate["passed"]
                and customer_pool_gate["passed"]
            ),
        },
        "gate3": {
            "new_filter_added": True,
            "filter_replaces_pool_scope": True,
            "min_survival_rate_after": after["aggregate"]["min_survival_rate"],
            "passed": after["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "core_baseline_metrics": core["by_window"],
        "core_aggregate": core["aggregate"],
        "before_variant": before,
        "after_variant": after,
        "before_metrics": {
            "aggregate": before["aggregate"],
            **{label: row["metrics"] for label, row in before["by_window"].items()},
        },
        "after_metrics": {
            "aggregate": after["aggregate"],
            **{label: row["metrics"] for label, row in after["by_window"].items()},
        },
        "delta_metrics": {
            "aggregate": gate4["aggregate_delta_vs_before"],
            "by_window": gate4["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": gate4["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "gate_results": gate4,
        "gate4": gate4,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space forward event labels remain too thin for LLM soft-ranking; "
                "this run uses deterministic event-seed metadata already logged for "
                "production observation."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": True,
            "parity_test_added": accepted,
            "daily_report_metadata_changed": accepted,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "alters_candidate_pool_scope": accepted,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not promote customer-win coverage into a hard Space "
            "pool filter on these frozen windows. Future Space work should favor "
            "forward replacement-value coverage or new official catalyst fields "
            "over pool pruning."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_002_space_customer_win_pool_scope.py",
            "data/experiments/exp-20260513-002/space_customer_win_pool_scope.json",
            "experiments/logs/exp-20260513-002.json",
            "experiments/tickets/exp-20260513-002.json",
            "experiments/artifacts/exp-20260513-002_space_customer_win_pool_scope.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "Nearby Space scalar retunes, LLM soft-ranking, noisy ticker expansion, "
            "theme ETF timing, and target-width retries are blocked by prior "
            "experiments. This tests a single production-visible candidate-pool "
            "quality rule derived from accepted customer-source evidence."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{STEM}.md"
    )
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        payload,
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "pnl_delta": result["delta_metrics"]["aggregate"]["total_pnl_sum"],
                "gate4_passed": result["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
