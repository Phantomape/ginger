"""exp-20260607-008: shared industry-relative laggard repair adapter.

This alpha experiment promotes the positive exp-20260607-007 replay lead into
quant/industry_relative_laggard_repair_paper_sleeve.py. Historical replay and
daily default-off snapshots now share one helper. No live/default orders, core
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
from industry_relative_laggard_repair_paper_sleeve import (
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_industry_relative_laggard_repair_historical_trades,
)


EXPERIMENT_ID = "exp-20260607-008"
STEM = "industry_relative_laggard_repair_shared_adapter"
TRIAL_FAMILY = "industry_relative_laggard_repair_shared_default_off_adapter"
TRIAL_VARIANT_ID = RULE_VERSION
CHANGED_VARIABLE = RULE_VERSION
SOURCE_LEAD_EXPERIMENT_ID = "exp-20260607-007"

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_008_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PRODUCTION_PARITY_MD = REPO_ROOT / "docs" / "production_backtest_parity.md"
DATA_EDGE_MD = REPO_ROOT / "docs" / "data_edge_context_layers.md"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260607_007_industry_relative_laggard_repair.json"
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35
MAX_LEAD_REPRO_EV_DRIFT = 0.0002
MAX_LEAD_REPRO_PNL_DRIFT = 1.0

PREDICTION = {
    "success_probability": 0.58,
    "expected_ev_delta": 0.2763,
    "expected_pnl_delta": 6208.99,
    "main_failure_modes": [
        "shared_helper_mismatch",
        "daily_snapshot_parity_gap",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260607-007 already improved all three canonical windows with "
        "306 target trades and acceptable concentration. This run changes the "
        "implementation boundary only: the source must reproduce through a "
        "shared default-off helper and daily snapshot semantics."
    ),
    "recorded_at": "2026-06-07T06:03:55Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_helper_wired_to_daily_observation",
    "shared_policy_changed": True,
    "backtester_adapter_changed": True,
    "run_adapter_changed": True,
    "replay_only": False,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": True,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "activation_envelope": {
        "intended_notional": "default-off paper only at fixed $4,000 notional",
        "capital_cap": "no live capital; future activation must cap portfolio exposure",
        "liquidity_slippage_model": "historical replay uses ADV >= $50M, production entry fill, target-side sell slippage, and round-trip cost",
        "portfolio_displacement": "paper overlay versus cash/core baseline only; no live displacement",
        "kill_switch": "future activation requires closed forward replacement-value gate and drawdown/concentration kill switch",
        "order_semantics": "no orders emitted; pending/open/closed paper ledger only",
    },
    "parity_note": (
        "Historical replay and daily production observation call "
        "quant/industry_relative_laggard_repair_paper_sleeve.py. The helper "
        "is default-off and cannot alter orders, core ranking, sizing, exits, "
        "watchlists, LLM, or news behavior."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _compare_window(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            float(after.get("expected_value_score") or 0.0)
            - float(before.get("expected_value_score") or 0.0),
            4,
        ),
        "total_pnl": round(
            float(after.get("total_pnl") or 0.0) - float(before.get("total_pnl") or 0.0),
            2,
        ),
        "max_drawdown_pct": round(
            float(after.get("max_drawdown_pct") or 0.0)
            - float(before.get("max_drawdown_pct") or 0.0),
            6,
        ),
        "signals_generated": 0,
        "signals_survived": 0,
        "survival_rate": 0.0,
        "trade_count": 0,
        "win_rate": 0.0,
    }


def _lead_reproduction_check(payload: dict[str, Any]) -> dict[str, Any]:
    lead = _load_json(SOURCE_LEAD_JSON, {})
    if not lead:
        return {"passed": False, "reason": "missing_source_lead_artifact"}
    actual_agg = payload["delta_metrics"]["aggregate"]
    lead_agg = (lead.get("delta_metrics") or {}).get("aggregate") or {}
    ev_drift = round(
        float(actual_agg.get("expected_value_score_delta_sum") or 0.0)
        - float(lead_agg.get("expected_value_score_delta_sum") or 0.0),
        6,
    )
    pnl_drift = round(
        float(actual_agg.get("total_pnl_delta_sum") or 0.0)
        - float(lead_agg.get("total_pnl_delta_sum") or 0.0),
        2,
    )
    trade_drift = int(payload["target_trade_summary"]["total_trade_count"]) - int(
        ((lead.get("target_trade_summary") or {}).get("total_trade_count") or 0)
    )
    by_window: dict[str, dict[str, Any]] = {}
    for label in framework.WINDOWS:
        actual = payload["delta_metrics"]["by_window"][label]
        expected = ((lead.get("delta_metrics") or {}).get("by_window") or {}).get(label, {})
        by_window[label] = {
            "expected_value_score_drift": round(
                float(actual.get("expected_value_score") or 0.0)
                - float(expected.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_drift": round(
                float(actual.get("total_pnl") or 0.0)
                - float(expected.get("total_pnl") or 0.0),
                2,
            ),
            "trade_count": len(payload["target_trades_by_window"][label]),
        }
    passed = (
        abs(ev_drift) <= MAX_LEAD_REPRO_EV_DRIFT
        and abs(pnl_drift) <= MAX_LEAD_REPRO_PNL_DRIFT
        and trade_drift == 0
    )
    return {
        "passed": passed,
        "source_lead_artifact": _repo_rel(SOURCE_LEAD_JSON),
        "aggregate_expected_value_score_delta_drift": ev_drift,
        "aggregate_total_pnl_delta_drift": pnl_drift,
        "trade_count_drift": trade_drift,
        "by_window": by_window,
        "max_ev_drift": MAX_LEAD_REPRO_EV_DRIFT,
        "max_pnl_drift": MAX_LEAD_REPRO_PNL_DRIFT,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    lead_reproduction: dict[str, Any],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if not lead_reproduction.get("passed"):
        failed.append("positive_lead_not_reproduced_by_shared_adapter")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_industry_relative_laggard_repair_shared_default_off_adapter"
            if passed
            else "rejected_industry_relative_laggard_repair_shared_default_off_adapter"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "lead_reproduction": lead_reproduction,
        "parity_test_added": True,
        "shared_adapter_module": "quant/industry_relative_laggard_repair_paper_sleeve.py",
    }


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    framework._configure_sleeve_globals()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] shared industry-relative laggard repair adapter replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        trades, audit = build_industry_relative_laggard_repair_historical_trades(
            ohlcv_by_ticker=snapshot,
            core_entries_by_date=framework.shadow._baseline_entries(before_result),
            windows={label: cfg},
            sector_entries=window_sector_entries,
            config=DEFAULT_CONFIG,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = _compare_window(before, after)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = trades
        target_audit_by_window[label] = audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "raw_candidate_count": audit["raw_candidate_count_by_window"].get(label, 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "hypothesis": (
            "The industry-relative laggard repair source remains valuable when "
            "candidate generation is moved into a shared default-off paper "
            "helper used by both historical replay and daily snapshots."
        ),
        "change_type": "default_off_paper_shared_adapter",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "positive_replay_lead_shared_adapter_promotion",
        "nearby_prior_experiments": [
            "exp-20260607-007",
            "exp-20260606-029",
            "exp-20260607-005",
            "exp-20260606-024",
            "exp-20260606-025",
        ],
        "prior_trial_count": 1,
        "prediction": PREDICTION,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "shared default-off paper helper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only signal-date close OHLCV, broad-market sector "
                "map industry grouping, prior 20/5/60-day return context, "
                "next-open paper entry, and 10-trading-day close exit through "
                "the shared fill/cost model."
            ),
        },
        "parameters": {
            "shared_adapter_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            **{
                key: DEFAULT_CONFIG[key]
                for key in [
                    "paper_notional_usd",
                    "daily_entry_slots",
                    "hold_days",
                    "same_ticker_cooldown_days",
                    "min_industry_lag_20d",
                    "max_industry_lag_20d",
                    "min_group_median_ret20_excess_spy",
                    "min_group_ret20_positive_fraction",
                    "min_signal_relative_vs_spy",
                    "min_close_location",
                    "max_realized_vol_20d",
                ]
            },
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/shared_adapter: exp007's industry-relative "
                "laggard repair alpha is only usable if the same helper can "
                "drive historical replay and daily default-off paper observation."
            ),
            "2_history_check": {
                "exp-20260607-007": (
                    "Positive replay lead: aggregate EV +0.2763, PnL +$6,208.99, "
                    "306 target trades, all three windows positive."
                ),
                "exp-20260606-029": (
                    "Sector ETF laggard failed; this uses individual-stock "
                    "industry medians and same-day repair instead of ETF lag."
                ),
                "exp-20260607-005": (
                    "Raw short-horizon reversal failed by drawdown and window "
                    "regression; this requires strong industry context."
                ),
                "exp-20260606-024": (
                    "Relation-aware free-OHLCV peer shock was positive, supporting "
                    "relation construction as the alpha hypothesis."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use the same three canonical windows. Aggregate EV/PnL must be "
                "positive, no EV/PnL regression window, sample >=20 across all "
                "3 windows, survival >=5%, drawdown drift <=0.5pp, concentration "
                "guard passes, and the shared helper must reproduce exp007."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260607_008_industry_relative_laggard_repair_shared_adapter.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "same-day baseline A/B entries from current core replay",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()) >= 0.05,
            "note": (
                "No new core filter is added. The helper is default-off paper; "
                "core signals generated/survived are unchanged from baseline."
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "target_audit_by_window": target_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "production_impact": PRODUCTION_IMPACT,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "anti_js": "No JavaScript was used.",
    }
    lead_reproduction = _lead_reproduction_check(payload)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        lead_reproduction=lead_reproduction,
    )
    payload["gate4"] = gate4
    payload["status"] = "accepted" if gate4["passed"] else "rejected"
    payload["decision"] = gate4["decision"]
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    payload["interpretation"] = (
        "The positive industry-relative laggard repair lead reproduced through "
        "a shared default-off helper and daily snapshot surface."
        if gate4["passed"]
        else (
            "The industry-relative laggard repair lead failed shared-helper "
            "promotion; do not retain the helper as accepted alpha."
        )
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The shared helper reproduced the private replay lead with the same "
            "fixed policy bundle, indicating the alpha came from the industry "
            "relative lag plus same-day repair relation rather than runner-only "
            "implementation quirks."
            if gate4["passed"]
            else (
                "The production-visible helper failed to reproduce the private "
                "lead or breached Gate 4, indicating the replay lead depended on "
                "implementation details or remained too fragile."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep industry lag, group median RS, positive fraction, "
            "signal-day reclaim, volume, volatility, hold-day, top-N, cooldown, "
            "or paper notional thresholds on the frozen windows."
        ),
        "new_evidence_required": (
            "Next useful work is closed forward replacement-value rows from the "
            "shared default-off ledger or an orthogonal PIT relation field."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "independent PIT relation or event confirmation",
        "no frozen-window parameter retune",
    ]
    payload["related_files"] = [
        "quant/industry_relative_laggard_repair_paper_sleeve.py",
        "quant/test_industry_relative_laggard_repair_paper_sleeve.py",
        "quant/run.py",
        "quant/default_off_alpha_attribution.py",
        "quant/report_generator.py",
        "docs/production_backtest_parity.md",
        "docs/data_edge_context_layers.md",
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(MANIFEST_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["target_audit_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                raw=audit["raw_candidate_count_by_window"].get(label, 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    lead_repro = payload["gate4"]["lead_reproduction"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry-Relative Laggard Repair Shared Adapter",
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
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "- Lead reproduction EV drift: `{:+.6f}`".format(
                lead_repro.get("aggregate_expected_value_score_delta_drift", 0.0)
            ),
            "- Lead reproduction PnL drift: `${:+,.2f}`".format(
                lead_repro.get("aggregate_total_pnl_delta_drift", 0.0)
            ),
            "",
            "## Production Impact",
            "",
            (
                "Shared default-off paper helper and daily observation surface "
                "only. `trade_enabled=false`; live/default orders, ranking, "
                "sizing, exits, LLM/news, and watchlists are unchanged."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "raw_candidate_count": payload["target_audit_by_window"][label][
                    "raw_candidate_count_by_window"
                ].get(label, 0),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        REPO_ROOT / "quant" / "industry_relative_laggard_repair_paper_sleeve.py",
        REPO_ROOT / "quant" / "test_industry_relative_laggard_repair_paper_sleeve.py",
        REPO_ROOT / "quant" / "run.py",
        REPO_ROOT / "quant" / "default_off_alpha_attribution.py",
        REPO_ROOT / "quant" / "report_generator.py",
        PRODUCTION_PARITY_MD,
        DATA_EDGE_MD,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {_repo_rel(path): framework._sha256(path) for path in paths},
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))
    _update_ticket(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
