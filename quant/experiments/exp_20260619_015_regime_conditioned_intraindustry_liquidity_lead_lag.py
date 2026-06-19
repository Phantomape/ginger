"""exp-20260619-015: regime-conditioned intra-industry liquidity lead-lag.

Replay-only alpha search. The single decision hypothesis is that the rejected
static broad-liquid intra-industry liquidity-leader lead-lag source
(exp-20260617-021) is not an always-on source: information diffusion from very
liquid industry leaders to lagging peers should pay only in weak/stress
markets, while strong-trend and choppy regimes create continuation or reversal
false positives.

The relation construction, broad liquid universe, next-open paper entry,
10-trading-day hold, costs, cooldown, daily top-1 selection, and all leader /
laggard thresholds are fixed from exp-20260617-021. The only decision change is
an entry-day PIT regime gate using the shared production-visible
quant.regime_chop_state helper: admit candidates only when the signal-date SPY
state is `risk_off_stress`.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared daily/backtest helper reproduces it. No
JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260617_021_intraindustry_liquidity_leader_lead_lag_scout as static
import regime_chop_state


EXPERIMENT_ID = "exp-20260619-015"
STEM = "regime_conditioned_intraindustry_liquidity_lead_lag"
TRIAL_FAMILY = "free_ohlcv_intraindustry_liquidity_leader_lead_lag_candidate_pool"
TRIAL_VARIANT_ID = "regime_chop_state_risk_off_stress_gate_top1_next_open_10d_v1"
CHANGED_VARIABLE = "regime_conditioned_intraindustry_liquidity_leader_lead_lag_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = static.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_015_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = static.BASE_NOTIONAL_USD
HOLD_DAYS = static.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = static.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = static.SAME_TICKER_COOLDOWN_DAYS

ADMITTED_REGIME_LABEL = "risk_off_stress"
REGIME_GATE = "entry_day_spy_risk_off_stress_only"
STATIC_SOURCE_RULE_VERSION = static.RULE_VERSION
_STATIC_CANDIDATE_ROWS_FOR_WINDOW = static._candidate_rows_for_window

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "old_thin_still_regresses",
        "regime_router_frozen_window_re_slice",
        "accepted_relation_comparator_not_beaten",
        "production_parity_not_promoted",
    ],
    "confidence_reason": (
        "The static source was positive only in the weak/transitional window "
        "and explicitly named shared PIT regime conditioning as the next "
        "non-threshold evidence axis. The risk is high because the protocol "
        "warns against retrofitting frozen windows and a risk_off-only gate may "
        "be too sparse."
    ),
    "recorded_at": "2026-06-19T17:17:52Z",
}

PRODUCTION_IMPACT = {
    **static.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "live_ready": False,
    "execution_envelope": {
        **static.PRODUCTION_IMPACT["execution_envelope"],
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "industry with fewer than 6 liquid members, missing leader basket, "
            "missing OHLCV, insufficient SPY regime lookback, non-risk_off SPY "
            "regime, missing next open, or missing 10d exit rejects the paper "
            "candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. It uses the existing "
        "shared PIT regime helper but remains replay-only because the "
        "intra-industry lead-lag source itself has no shared daily/backtest "
        "adapter. A positive result is only a lead until a shared default-off "
        "helper computes the same broad-universe industry leader basket, "
        "diffusion-gap laggard gate, SPY regime tag, next-open paper entry, "
        "10-day exit, costs, cooldown, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/risk_allocation: the broad-liquid intra-industry "
        "liquidity-leader lead-lag source is state-dependent. Its diffusion "
        "edge should appear during weak/stress markets, so this test admits the "
        "fixed exp-20260617-021 candidate source only when shared PIT "
        "regime_chop_state_v1 labels the signal date risk_off_stress."
    ),
    "2_history_check": {
        "exp-20260617-021": (
            "Static always-on source rejected despite positive aggregate; paid "
            "in mid_weak but regressed in late_strong and old_thin. Its "
            "closeout identified regime-conditioned deployment as the valid "
            "next evidence axis, not threshold sweeps."
        ),
        "exp-20260618-006": (
            "PIT direction-stability refinement rejected due old_thin regression "
            "and drawdown drift. This run does not change relation thresholds or "
            "direction-stability; it applies a shared entry-day market regime "
            "condition to the fixed source."
        ),
        "exp-20260615-025": (
            "Shared regime_chop_state_v1 replay/daily adapter validation exists. "
            "This experiment uses that helper read-only; it does not change the "
            "helper or production execution."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. A positive "
        "replay remains unaccepted until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_015_regime_conditioned_intraindustry_liquidity_lead_lag.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return static._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return static._round(value, digits)


def _regime_payload_for_date(
    *,
    spy_rows: list[dict[str, Any]],
    signal_date: str,
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    cached = cache.get(signal_date)
    if cached is not None:
        return cached
    payload = regime_chop_state.regime_chop_from_spy_universe(spy_rows, signal_date)
    cache[signal_date] = payload
    return payload


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    old_static_rule = static.RULE_VERSION
    static.RULE_VERSION = STATIC_SOURCE_RULE_VERSION
    try:
        static_rows, static_scan = _STATIC_CANDIDATE_ROWS_FOR_WINDOW(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
            quality_index=quality_index,
        )
    finally:
        static.RULE_VERSION = old_static_rule

    spy_rows = static.base.framework.shadow._series(snapshot, "SPY")
    regime_cache: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    admitted: list[dict[str, Any]] = []

    for row in static_rows:
        signal_date = str(row["date"])[:10]
        regime_state = _regime_payload_for_date(
            spy_rows=spy_rows,
            signal_date=signal_date,
            cache=regime_cache,
        )
        label = str(regime_state.get("regime_label") or "unknown")
        counts[f"regime_candidate_rows_{label}"] += 1
        counts[f"regime_signal_days_{label}"] += 0
        if label != ADMITTED_REGIME_LABEL:
            counts["regime_rejected_candidate_rows"] += 1
            continue

        counts["regime_admitted_candidate_rows"] += 1
        out = dict(row)
        out.update(
            {
                "source": "REGIME_CONDITIONED_INTRAINDUSTRY_LIQUIDITY_LEAD_LAG_PAPER",
                "rule_version": RULE_VERSION,
                "source_rule_version": RULE_VERSION,
                "static_source_rule_version": STATIC_SOURCE_RULE_VERSION,
                "regime_rule_version": regime_chop_state.RULE_VERSION,
                "regime_gate": REGIME_GATE,
                "entry_regime_label": label,
                "entry_regime_coverage": regime_state.get("coverage"),
                "entry_regime_exposure_scalar": regime_state.get("exposure_scalar"),
                "entry_regime_p_risk_on_trend": regime_state.get("p_risk_on_trend"),
                "entry_regime_p_choppy_range": regime_state.get("p_choppy_range"),
                "entry_regime_p_risk_off_stress": regime_state.get("p_risk_off_stress"),
                "entry_regime_bull_score": regime_state.get("bull_score"),
                "entry_regime_risk_off_score": regime_state.get("risk_off_score"),
                "entry_regime_known_at": "signal_close_spy_ohlcv_before_next_open_paper_entry",
            }
        )
        admitted.append(out)

    signal_days_by_label: Counter[str] = Counter()
    for d, state in regime_cache.items():
        signal_days_by_label[str(state.get("regime_label") or "unknown")] += 1
    for label, count in signal_days_by_label.items():
        counts[f"regime_signal_days_{label}"] = count

    scan = dict(static_scan)
    scan.update(
        {
            "static_source_rule_version": STATIC_SOURCE_RULE_VERSION,
            "rule_version": RULE_VERSION,
            "regime_rule_version": regime_chop_state.RULE_VERSION,
            "regime_gate": REGIME_GATE,
            "static_candidate_rows_before_regime_gate": len(static_rows),
            "deduped_candidate_rows": len(admitted),
            "candidate_signal_days": len({row["date"] for row in admitted}),
            "candidate_tickers": len({row["ticker"] for row in admitted}),
            "regime_unique_signal_days_evaluated": len(regime_cache),
            **dict(counts),
        }
    )
    admitted.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["leadlag_diffusion_gap"] or 0.0),
            -float(row["leadlag_leader_excess_ret10"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    return admitted, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = static.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= static.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= static.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= static.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= static.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = static.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = static.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_regime_conditioned_intraindustry_liquidity_lead_lag"
        if gate["passed"]
        else "rejected_regime_conditioned_intraindustry_liquidity_lead_lag_candidate_pool"
    )
    return gate


def _configure_static_parent() -> None:
    static.EXPERIMENT_ID = EXPERIMENT_ID
    static.STEM = STEM
    static.TRIAL_FAMILY = TRIAL_FAMILY
    static.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    static.CHANGED_VARIABLE = CHANGED_VARIABLE
    static.RULE_VERSION = RULE_VERSION
    static.OWNER = OWNER
    static.OUT_DIR = OUT_DIR
    static.OUT_JSON = OUT_JSON
    static.LOG_JSON = LOG_JSON
    static.TICKET_JSON = TICKET_JSON
    static.CARD_MD = CARD_MD
    static.MANIFEST_JSON = MANIFEST_JSON
    static.EXPERIMENT_LOG = EXPERIMENT_LOG
    static.REGISTRY_JSON = REGISTRY_JSON
    static.PREDICTION = PREDICTION
    static.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    static.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    static._candidate_rows_for_window = _candidate_rows_for_window
    static._gate4 = _gate4
    static._configure_base()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    by_window = payload["delta_metrics"]["by_window"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    target_summary = payload["target_trade_summary"]

    if gate4["passed"]:
        interpretation = (
            "The risk_off_stress regime gate cleared the numeric three-window "
            "screen for the static intra-industry liquidity-leader lead-lag "
            "source, but remains only a replay lead because the source itself "
            "has no shared daily/backtest adapter."
        )
    else:
        interpretation = (
            "The risk_off_stress regime gate did not rescue the static "
            "intra-industry liquidity-leader lead-lag source. Gate 4 failed on "
            f"{', '.join(gate4['failed_reasons']) or 'none'}. Three-window "
            "deltas: late_strong dEV {late_ev:+.4f}, dPnL ${late_pnl:+,.2f}; "
            "mid_weak dEV {mid_ev:+.4f}, dPnL ${mid_pnl:+,.2f}; old_thin dEV "
            "{old_ev:+.4f}, dPnL ${old_pnl:+,.2f}. The economic read is that "
            "risk_off-only selection is either too sparse or captures stress "
            "laggards after the leader move when catch-up is not reliable "
            "enough after costs; it does not produce a stable production-ready "
            "candidate source."
        ).format(
            late_ev=by_window["late_strong"].get("expected_value_score", 0.0),
            late_pnl=by_window["late_strong"].get("total_pnl", 0.0),
            mid_ev=by_window["mid_weak"].get("expected_value_score", 0.0),
            mid_pnl=by_window["mid_weak"].get("total_pnl", 0.0),
            old_ev=by_window["old_thin"].get("expected_value_score", 0.0),
            old_pnl=by_window["old_thin"].get("total_pnl", 0.0),
        )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_free_ohlcv_intraindustry_lead_lag_relation_candidate_pool"
            ),
            "new_evidence_type": "shared_pit_regime_conditioned_free_ohlcv_relation_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260617-021",
                "exp-20260618-006",
                "exp-20260615-025",
            ],
            "prior_trial_count": 2,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "lead_lookback_days": static.LEAD_LOOKBACK_DAYS,
        "leader_top_k": static.LEADER_TOP_K,
        "min_industry_members": static.MIN_INDUSTRY_MEMBERS,
        "min_leader_excess_ret": static.MIN_LEADER_EXCESS_RET,
        "min_diffusion_gap": static.MIN_DIFFUSION_GAP,
        "max_candidate_excess_ret": static.MAX_CANDIDATE_EXCESS_RET,
        "min_candidate_ret": static.MIN_CANDIDATE_RET,
        "min_price": static.MIN_PRICE,
        "min_avg_dollar_volume_20d": static.MIN_AVG_DOLLAR_VOLUME_20D,
        "regime_rule_version": regime_chop_state.RULE_VERSION,
        "regime_gate": REGIME_GATE,
        "admitted_regime_label": ADMITTED_REGIME_LABEL,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "First compute the fixed exp-20260617-021 broad-liquid intra-industry "
        "liquidity-leader lead-lag candidates from PIT OHLCV and sector/"
        "industry metadata. Then compute the shared regime_chop_state_v1 state "
        "from SPY bars known at the signal close. Only candidates whose signal "
        "date is labelled risk_off_stress survive to the existing top-1 "
        "next-open paper entry, 10-trading-day exit, costs, and cooldown "
        "simulation. No leader, laggard, hold, notional, ranking, or cooldown "
        "threshold is changed."
    )
    payload["gate2"]["runtime_fields"] = [
        "warehouse OHLCV Date/Open/High/Low/Close/Volume (broad liquid universe)",
        "SPY OHLCV for relative strength and shared regime_chop_state_v1",
        "broad_market_sector_map industry/sector membership",
        "derived 10d excess return and 20d dollar volume per ticker",
        "entry-day PIT regime_label and regime probabilities",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "Do not retry this same frozen-window regime re-slice by changing "
        "risk_off/chop/on labels or probability thresholds. A valid next step "
        "needs closed forward replacement-value rows tagged with entry-time "
        "regime, a shared default-off daily/backtest adapter for the source, or "
        "a materially different relation provenance such as customer/supplier "
        "links or a non-OHLCV relation graph."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                target_summary["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping admitted regime labels, regime probability "
            "thresholds, leader-top-K, min-leader-excess, diffusion-gap, "
            "candidate-excess cap, candidate-ret floor, lookback, industry-member "
            "minimum, price/ADV floors, top-N, hold days, cooldown, or notional "
            "on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Static Rows | Regime Rows | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in static.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {static_rows} | {regime_rows} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                static_rows=scan.get("static_candidate_rows_before_regime_gate", 0),
                regime_rows=scan.get("regime_admitted_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Regime-Conditioned Intra-Industry Liquidity Lead-Lag",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Regime gate: `{}`".format(REGIME_GATE),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. The shared regime helper "
                "is called read-only, but no shared lead-lag adapter, run adapter, "
                "backtester adapter, production watchlist, order path, core entry, "
                "ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): static.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): static.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): static.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): static.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): static.base.framework._sha256(CARD_MD),
        },
    }
    static.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = static.base._build_log_record(payload)
    static.base.framework._write_json(OUT_JSON, payload)
    static.base.framework._write_json(LOG_JSON, payload)
    static.base.framework._write_text(CARD_MD, _build_card(payload))
    static.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    static.base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    _configure_static_parent()
    payload = _postprocess_payload(static.base._build_payload())
    _persist(payload)
    print(json.dumps(static.base.framework._safe(static.base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
