"""exp-20260610-008: 52-week-high proximity core-flow full-stack promotion.

Full-stack candidate-pool experiment (docs/agent_experiment_protocol.md ->
"Full-Stack Candidate-Pool Contract"). It promotes the positive exp-20260610-007
replay lead into quant/fiftytwo_week_high_proximity_paper_sleeve.py so that
historical replay and daily default-off snapshots share one helper, declares
the live-realistic execution envelope, designs and parity-tests the sleeve kill
switch, and records the standardized full-stack verdict.

No live/default orders, core ranking, sizing, exits, LLM/news path, or
watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from experiment_registry import persist_self_registered_result  # noqa: E402
from fiftytwo_week_high_proximity_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_fiftytwo_week_high_proximity_historical_trades,
)
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260610-008"
STEM = "fiftytwo_week_high_proximity_full_stack"
TRIAL_FAMILY = "fiftytwo_week_high_proximity_breakout_candidate_pool"
TRIAL_VARIANT_ID = RULE_VERSION
CHANGED_VARIABLE = (
    "shared_fiftytwo_week_high_proximity_core_flow_default_off_adapter_v1"
)
SOURCE_LEAD_EXPERIMENT_ID = "exp-20260610-007"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_008_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PRODUCTION_PARITY_MATRIX_MD = REPO_ROOT / "docs" / "production_backtest_parity_matrix.md"
DATA_EDGE_CATALOG_MD = REPO_ROOT / "docs" / "data_edge_context_layers_catalog.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260610_007_fiftytwo_week_high_proximity_core_flow.json"
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35
MAX_LEAD_REPRO_EV_DRIFT = 0.0002
MAX_LEAD_REPRO_PNL_DRIFT = 1.0

# Candidate snapshot lookback so the trailing 252-trading-day high is always
# computable inside the canonical windows. Past PIT bars only; never future.
SNAPSHOT_LOOKBACK_CALENDAR_DAYS = 470

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
    "target_trade_count": 44,
}
ACCEPTED_CORE_FLOW_COMPARATOR = {
    "experiment_id": "exp-20260608-008",
    "decision": "accepted_industry_stable_core_flow_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1459,
    "total_pnl_delta_sum": 3731.54,
    "target_trade_count": 47,
}

PREDICTION = {
    "success_probability": 0.62,
    "expected_ev_delta": 0.4308,
    "expected_pnl_delta": 9295.34,
    "main_failure_modes": [
        "shared_helper_drift",
        "window_regression",
        "production_parity_gap",
        "concentration_failed",
    ],
    "confidence_reason": (
        "The fixed exp-20260610-007 bundle already improved all three canonical "
        "windows and beat both accepted comparators; the main remaining risk is "
        "implementation drift when moving from private runner logic to shared "
        "default-off helper semantics, the same risk profile exp-20260609-027 "
        "carried at 0.62."
    ),
    "recorded_at": "2026-06-10T05:48:57+00:00",
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=4_000.0,
    max_capital_pct=0.40,
    min_dollar_volume=75_000_000.0,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=10,
    order_semantics="next_open",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Top-1/day with a 10-trading-day hold bounds concurrency at 10 paper "
        "positions x $4,000 = $40,000 committed paper capital (40% of the "
        "$100,000 backtest equity base). Kill switch (8% of committed capital "
        "realized peak-to-trough drawdown, hard) and sleeve drawdown stop (5%, "
        "soft) plus a positive-PnL concentration kill are implemented in "
        "quant/fiftytwo_week_high_proximity_paper_sleeve.py and parity-tested; "
        "when triggered the sleeve stops creating new pending paper entries. "
        "All values declared up front so live promotion is a checklist item, "
        "not a new alpha search."
    ),
)

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_helper_with_daily_snapshot_api",
    "shared_policy_changed": True,
    "backtester_adapter_changed": True,
    "run_adapter_changed": False,
    "replay_only": False,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": True,
    "daily_snapshot_note": (
        "quant/fiftytwo_week_high_proximity_paper_sleeve.py exposes the daily "
        "default-off snapshot API. quant/run.py is intentionally unchanged in "
        "this experiment because live/default order paths must remain untouched."
    ),
    "history_parity_note": (
        "The candidate rule needs >= 252 prior trading days of OHLCV. With "
        "less history the rule fails closed in both historical replay and "
        "daily snapshots: the ticker simply cannot qualify. Historical replay "
        "loads a deep snapshot (470 calendar days of lookback) of past bars "
        "only; no future data is read."
    ),
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "Historical replay and daily observation share "
        "quant/fiftytwo_week_high_proximity_paper_sleeve.py. The helper is "
        "default-off and cannot alter orders, core ranking, sizing, exits, "
        "watchlists, LLM, or news behavior. The sleeve kill switch only stops "
        "new paper entries; it never touches orders."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: anchoring underreaction at the 52-week high "
        "(George-Hwang 2004) makes liquid sector-known stocks that push into a "
        "fresh 52-week-high zone with SPY-relative leadership and close/volume "
        "quality continue after next-open entry, when the same day has core A/B "
        "entry flow and same-ticker overlap is excluded. exp-20260610-007 "
        "showed this as a positive free-OHLCV replay lead; exp-20260610-008 "
        "tests whether the fixed policy bundle survives shared default-off "
        "historical/daily semantics and completes the full-stack contract."
    ),
    "2_history_check": {
        "exp-20260610-007": (
            "Positive replay lead: aggregate EV +0.4308, PnL +$9,295.34, 54 "
            "target trades, all three canonical windows positive, drawdown "
            "drift +0.0027, concentration passed, and both accepted "
            "compression/core-flow comparators beaten. Not promoted because no "
            "shared helper, daily snapshot, parity test, envelope, or kill "
            "switch existed."
        ),
        "exp-20260609-027": (
            "Accepted turn-of-month shared adapter: the closest precedent for "
            "promoting a positive lead into a shared default-off helper with "
            "zero EV/PnL/trade drift."
        ),
        "exp-20260608-013": (
            "Accepted narrow-range compression shared adapter (EV +0.1608, "
            "PnL +$2,248.98); must remain beaten."
        ),
        "exp-20260608-008": (
            "Accepted industry-stable core-flow shared adapter (EV +0.1459, "
            "PnL +$3,731.54); the closest accepted core-flow relation "
            "comparator; must remain beaten."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL must "
        "be positive, no EV/PnL regression window, sample >=20 across all 3 "
        "windows, survival >=5%, drawdown drift <=0.5pp, concentration guard "
        "passes, accepted compression and core-flow comparators remain beaten, "
        "the shared helper must reproduce exp-20260610-007 within drift "
        "tolerance, and the full-stack verdict is recorded with the declared "
        "execution envelope and parity-tested kill switch. Per "
        "docs/agent_experiment_protocol.md, evaluate_gate4 runs both strict "
        "(check_materiality=True, for the record) and canonical "
        "(check_materiality=False, for the decision); the binding materiality "
        "standard for candidate-pool sources is beating the closest accepted "
        "comparator after costs."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_008_fiftytwo_week_high_proximity_full_stack.py"
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


def _load_window_snapshot_deep(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Window snapshot with >= 252 trading days of lookback (past bars only)."""
    start = framework._parse_date(cfg["start"]) - timedelta(
        days=SNAPSHOT_LOOKBACK_CALENDAR_DAYS
    )
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(framework.WAREHOUSE) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


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
    lead_by_window = (lead.get("delta_metrics") or {}).get("by_window") or {}
    for label in framework.WINDOWS:
        actual = payload["delta_metrics"]["by_window"][label]
        expected = lead_by_window.get(label, {})
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
            "target_trade_count": len(payload["target_trades_by_window"][label]),
            "source_target_trade_count": len(
                ((lead.get("target_trades_by_window") or {}).get(label)) or []
            ),
        }
    passed = (
        abs(ev_drift) <= MAX_LEAD_REPRO_EV_DRIFT
        and abs(pnl_drift) <= MAX_LEAD_REPRO_PNL_DRIFT
        and trade_drift == 0
    )
    return {
        "passed": passed,
        "source_lead_experiment_id": SOURCE_LEAD_EXPERIMENT_ID,
        "source_lead_artifact": _repo_rel(SOURCE_LEAD_JSON),
        "aggregate_expected_value_score_delta_drift": ev_drift,
        "aggregate_total_pnl_delta_drift": pnl_drift,
        "trade_count_drift": trade_drift,
        "by_window": by_window,
        "max_ev_drift": MAX_LEAD_REPRO_EV_DRIFT,
        "max_pnl_drift": MAX_LEAD_REPRO_PNL_DRIFT,
    }


def _gate4_canonical(
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
    for name, comparator in (
        ("compression", ACCEPTED_COMPRESSION_COMPARATOR),
        ("core_flow", ACCEPTED_CORE_FLOW_COMPARATOR),
    ):
        if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= comparator[
            "expected_value_score_delta_sum"
        ]:
            failed.append(f"accepted_{name}_ev_not_beaten")
        if float(aggregate["total_pnl_delta_sum"] or 0.0) <= comparator[
            "total_pnl_delta_sum"
        ]:
            failed.append(f"accepted_{name}_pnl_not_beaten")
    if not lead_reproduction.get("passed"):
        failed.append("positive_lead_not_reproduced_by_shared_adapter")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter"
            if passed
            else "rejected_fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter"
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
        "accepted_comparators": {
            "compression": ACCEPTED_COMPRESSION_COMPARATOR,
            "core_flow": ACCEPTED_CORE_FLOW_COMPARATOR,
        },
        "lead_reproduction": lead_reproduction,
        "parity_test_added": True,
        "shared_adapter_module": "quant/fiftytwo_week_high_proximity_paper_sleeve.py",
    }


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted(positive.values(), reverse=True)[:5])
    return round(top5 / total, 6)


def _full_stack_blocks(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    trades = int(target_summary["total_trade_count"] or 0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    notional = float(DEFAULT_CONFIG["paper_notional_usd"])
    window_metrics = {
        "aggregate_ev_delta": float(aggregate["expected_value_score_delta_sum"] or 0.0),
        "aggregate_pnl_delta": pnl_delta,
        "windows_ev_improved": int(aggregate["windows_ev_improved"] or 0),
        "windows_ev_regressed": int(aggregate["windows_ev_regressed"] or 0),
        "adjusted_trade_count": trades,
        "adjusted_window_count": len(target_summary["windows_with_target_trades"]),
        "max_drawdown_worse_max": max(
            0.0, float(aggregate["max_drawdown_delta_max"] or 0.0)
        ),
        "single_ticker_positive_share": target_summary["max_single_positive_pnl_share"],
        "baseline_single_ticker_positive_share": MAX_SINGLE_POSITIVE_SHARE,
        "top_5_contribution_pct": _top5_positive_share(target_summary),
        "baseline_top_5_contribution_pct": 0.60,
        "hhi_concentration": target_summary["positive_pnl_hhi"],
        "baseline_hhi_concentration": MAX_POSITIVE_HHI,
        "avg_pnl_per_trade_delta": round(pnl_delta / trades, 2) if trades else None,
        "avg_return_delta_pp": (
            round(pnl_delta / (trades * notional) * 100.0, 4) if trades else None
        ),
    }
    gate4_strict = evaluate_gate4(window_metrics, check_materiality=True)
    gate4_canonical = evaluate_gate4(window_metrics, check_materiality=False)
    return {
        "window_metrics": window_metrics,
        "gate4_strict_materiality": gate4_strict,
        "gate4_canonical": gate4_canonical,
        "materiality_note": (
            "Per docs/agent_experiment_protocol.md, the scout materiality floor "
            "($500/trade or 5pp) is calibrated for support-field/notional-scalar "
            "scouts; at the fixed $4,000 candidate-pool paper notional it would "
            "reject every accepted comparator. The binding materiality standard "
            "for candidate-pool sources is beating the closest accepted "
            "comparator after costs, which this run enforces in the canonical "
            "framework Gate 4. Both evaluate_gate4 blocks are recorded."
        ),
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
        print(f"[{label}] shared 52-week-high proximity core-flow adapter replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = _load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = {
            "status": "warehouse_sector_known_liquid_common_stock_like_universe",
            "tickers": sorted(window_sector_entries),
            "records": window_sector_entries,
        }
        trades, audit = build_fiftytwo_week_high_proximity_historical_trades(
            ohlcv_by_ticker=snapshot,
            core_entries_by_date=framework.shadow._baseline_entries(before_result),
            windows={label: cfg},
            candidate_universe=candidate_universe,
            config=DEFAULT_CONFIG,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = trades
        target_audit_by_window[label] = audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
            "snapshot_lookback_calendar_days": SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
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
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "positive_replay_lead_full_stack_promotion",
        "nearby_prior_experiments": [
            "exp-20260610-007",
            "exp-20260609-027",
            "exp-20260608-013",
            "exp-20260608-008",
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
                "Signal uses only free signal-date OHLCV with >= 252 prior "
                "trading days of history: close within 3% of the trailing "
                "252-day high, a new 60-day-high breakout, SPY-relative "
                "leadership, close/volume/volatility guards, same-day core A/B "
                "entry-flow confirmation, same-ticker selected-core overlap "
                "exclusion, top-1/day, next-open paper entry, and "
                "10-trading-day close exit through the shared fill/cost model."
            ),
        },
        "parameters": {
            "shared_adapter_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "snapshot_lookback_calendar_days": SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
            **{
                key: DEFAULT_CONFIG[key]
                for key in [
                    "paper_notional_usd",
                    "daily_entry_slots",
                    "max_active_positions",
                    "hold_days",
                    "same_ticker_cooldown_days",
                    "min_price",
                    "min_avg_dollar_volume_20d",
                    "high_252_lookback",
                    "new_high_breakout_lookback",
                    "min_proximity_to_52w_high",
                    "min_ret20_excess_spy",
                    "min_ret60_excess_spy",
                    "min_signal_return",
                    "min_close_location",
                    "min_volume_ratio_20d",
                    "max_volume_ratio_20d",
                    "min_ret5",
                    "max_ret5",
                    "max_realized_vol_20d",
                    "kill_switch_drawdown_pct",
                    "sleeve_drawdown_stop_pct",
                ]
            },
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
            "standard_windows": framework.WINDOWS,
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                ">= 252 prior trading days of candidate OHLCV (fails closed otherwise)",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "same-day baseline A/B entries for core-flow confirmation",
                "same-day core A/B ticker for same-ticker overlap exclusion",
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
            "passed": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            )
            >= 0.05,
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
    gate4 = _gate4_canonical(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        lead_reproduction=lead_reproduction,
    )
    payload["gate4"] = gate4

    full_stack = _full_stack_blocks(aggregate=aggregate, target_summary=target_summary)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=True,
    )
    verdict = full_stack_verdict(
        gate4=full_stack["gate4_canonical"],
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    if not gate4["passed"]:
        verdict = {
            **verdict,
            "verdict": "reject",
            "gate4_passed": False,
            "next_step": (
                "Roll back the sleeve change and log the failure. The canonical "
                "framework Gate 4 (comparators + lead reproduction) did not pass."
            ),
        }
    payload["full_stack"] = {
        **full_stack,
        "live_readiness": live_readiness,
        "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
        "verdict": verdict,
    }
    payload["full_stack_verdict"] = verdict["verdict"]

    accepted = gate4["passed"] and verdict["verdict"] != "reject"
    payload["status"] = "accepted_paper_pending_forward" if accepted else "rejected"
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
        "The positive 52-week-high proximity core-flow lead reproduced through "
        "a shared default-off helper and daily snapshot API, with a declared "
        "execution envelope and parity-tested kill switch; the full-stack "
        "verdict is accepted_paper_pending_forward."
        if accepted
        else (
            "The 52-week-high proximity core-flow lead failed full-stack "
            "promotion; do not retain the helper as accepted alpha."
        )
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The shared helper reproduced the private replay lead because it "
            "kept the exact 252-day-high proximity, 60-day breakout, leadership "
            "and quality gates, core-flow admission, same-ticker overlap "
            "exclusion, next-open entry, 10-day exit, cost, top-1, and cooldown "
            "semantics while adding daily pending/open/closed state handling, "
            "a fail-closed >=252-day history requirement, and a realized-"
            "drawdown kill switch that only blocks new paper entries."
            if accepted
            else (
                "The helper failed reproduction or Gate 4, indicating the "
                "positive replay lead depended on implementation details or "
                "remained too fragile after shared daily semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep the 52-week proximity threshold, 252-day/60-day "
            "lookbacks, ret20/ret60 leadership thresholds, signal-day return, "
            "close-location, volume bounds, volatility bounds, top-N, hold-day, "
            "cooldown, or paper notional on the frozen windows."
        ),
        "new_evidence_required": (
            "Next useful evidence is closed forward replacement-value rows from "
            "the shared default-off ledger, or a genuinely new point-in-time "
            "field separating durable 52-week-high leaders from exhausted ones "
            "(fundamental quality, options/borrow structure), not another "
            "threshold retune."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "durable-vs-exhausted 52-week-high separator field",
        "no frozen-window parameter retune",
    ]
    payload["related_files"] = [
        "quant/fiftytwo_week_high_proximity_paper_sleeve.py",
        "quant/test_fiftytwo_week_high_proximity_paper_sleeve.py",
        "docs/production_backtest_parity_matrix.md",
        "docs/data_edge_context_layers_catalog.md",
        "docs/alpha-optimization-playbook.md",
        "docs/experiment_registry.json",
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(MANIFEST_JSON),
    ]
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
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
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    lead_repro = payload["gate4"]["lead_reproduction"]
    verdict = payload["full_stack"]["verdict"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} 52-Week-High Proximity Core-Flow Full-Stack Adapter",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{verdict['verdict']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2),
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Lead reproduction EV drift: `{:+.6f}`".format(
                lead_repro.get("aggregate_expected_value_score_delta_drift", 0.0)
            ),
            "- Lead reproduction PnL drift: `${:+,.2f}`".format(
                lead_repro.get("aggregate_total_pnl_delta_drift", 0.0)
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Full-Stack Contract",
            "",
            "- Strict materiality gate4 (record): `{}`".format(
                payload["full_stack"]["gate4_strict_materiality"]["status"]
            ),
            "- Canonical gate4 (decision): `{}`".format(
                payload["full_stack"]["gate4_canonical"]["status"]
            ),
            "- Live readiness blockers: `{}`".format(
                ", ".join(payload["full_stack"]["live_readiness"]["blockers"]) or "none"
            ),
            "- Execution envelope complete: `{}`".format(
                payload["full_stack"]["execution_envelope"]["complete"]
            ),
            "- Next step: {}".format(verdict["next_step"]),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            PRODUCTION_IMPACT["history_parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_artifact(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Artifact",
            "",
            "## Decision",
            "",
            f"`{payload['decision']}` (full-stack verdict: `{payload['full_stack_verdict']}`)",
            "",
            "## Fixed Policy Bundle",
            "",
            (
                "Liquid sector-known stock universe, close within 3% of the "
                "trailing 252-trading-day high AND a new 60-day-high breakout, "
                "20-day SPY-relative leadership, signal-day return, close "
                "location, volume and volatility guards, same-day core A/B "
                "entry-flow confirmation, same-ticker selected-core overlap "
                "exclusion, top-1/day, fixed $4,000 paper notional, next-open "
                "entry, 10-trading-day close exit, slippage, round-trip cost, "
                "and 10-trading-day same-ticker cooldown."
            ),
            "",
            "## Three-Window Before/After",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Gate failures: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Full-Stack Contract Blocks",
            "",
            "```json",
            json.dumps(
                {
                    "window_metrics": payload["full_stack"]["window_metrics"],
                    "gate4_strict_materiality": {
                        "status": payload["full_stack"]["gate4_strict_materiality"]["status"],
                        "hard_failures": payload["full_stack"]["gate4_strict_materiality"][
                            "hard_failures"
                        ],
                    },
                    "gate4_canonical": {
                        "status": payload["full_stack"]["gate4_canonical"]["status"],
                        "hard_failures": payload["full_stack"]["gate4_canonical"][
                            "hard_failures"
                        ],
                    },
                    "materiality_note": payload["full_stack"]["materiality_note"],
                    "live_readiness": payload["full_stack"]["live_readiness"],
                    "execution_envelope": payload["full_stack"]["execution_envelope"],
                    "verdict": payload["full_stack"]["verdict"]["verdict"],
                    "next_step": payload["full_stack"]["verdict"]["next_step"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Production Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            PRODUCTION_IMPACT["history_parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "full_stack_verdict": payload["full_stack_verdict"],
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "full_stack": {
            "verdict": payload["full_stack"]["verdict"],
            "live_readiness": payload["full_stack"]["live_readiness"],
            "execution_envelope": payload["full_stack"]["execution_envelope"],
            "gate4_strict_materiality_status": payload["full_stack"][
                "gate4_strict_materiality"
            ]["status"],
            "gate4_canonical_status": payload["full_stack"]["gate4_canonical"]["status"],
            "materiality_note": payload["full_stack"]["materiality_note"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
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
        "pre_run_questions": PRE_RUN_QUESTIONS,
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
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "artifact_md": _repo_rel(ARTIFACT_MD),
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


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["gate4"]["passed"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "artifact_md": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        QUANT_ROOT / "fiftytwo_week_high_proximity_paper_sleeve.py",
        QUANT_ROOT / "test_fiftytwo_week_high_proximity_paper_sleeve.py",
        PRODUCTION_PARITY_MATRIX_MD,
        DATA_EDGE_CATALOG_MD,
        PLAYBOOK_MD,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        ARTIFACT_MD,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in paths
            if path.exists()
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._write_text(ARTIFACT_MD, _build_artifact(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
