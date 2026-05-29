"""exp-20260529-012: cash-conversion sleeve closed-ledger governor.

Alpha search follow-up to exp-20260528-006. This keeps the PIT SEC
Companyfacts cash-conversion + OHLCV RS candidate source fixed, then changes
one launch-readiness variable: apply the accepted closed-paper-ledger
profit-cap/drawdown governor from exp-20260528-008 to the cash-conversion
paper sleeve.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_006_fundamental_growth_rs_cash_conversion_quality as source
import exp_20260528_008_operating_profit_quality_closed_ledger_governor as governor


EXPERIMENT_ID = "exp-20260529-012"
STEM = "fundamental_cash_conversion_closed_ledger_governor"
TRIAL_FAMILY = "fundamental_growth_rs_cash_conversion_launch_governor"
CHANGED_VARIABLE = "cash_conversion_closed_ledger_profit_cap_drawdown_governor_v1"
RULE_VERSION = "cash_conversion_closed_ledger_governor_v1"

TICKER_CLOSED_PROFIT_CAP_USD = 9_000.0
TICKER_PROFIT_CAP_SCALAR = 0.05
GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD = 7_500.0
GLOBAL_DRAWDOWN_SCALAR = 0.25

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260529_012_fundamental_cash_conversion_closed_ledger_governor.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REFERENCE_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260528-006.json"


def _base():
    return source.prev.base


def _configure_modules() -> None:
    source.EXPERIMENT_ID = EXPERIMENT_ID
    source.STEM = STEM
    source.TRIAL_FAMILY = TRIAL_FAMILY
    source.CHANGED_VARIABLE = CHANGED_VARIABLE
    source.RULE_VERSION = RULE_VERSION
    source.OUT_DIR = OUT_DIR
    source.OUT_JSON = OUT_JSON
    source.LOG_JSON = LOG_JSON
    source.TICKET_JSON = TICKET_JSON
    source.DOC_TICKET_JSON = DOC_TICKET_JSON
    source.ARTIFACT_MD = ARTIFACT_MD
    source.EXPERIMENT_LOG = EXPERIMENT_LOG
    source.CASH_QUALITY_AUDIT.clear()
    source.CASH_INDEX = None
    source._configure_modules()

    governor.source = source
    governor.EXPERIMENT_ID = EXPERIMENT_ID
    governor.STEM = STEM
    governor.TRIAL_FAMILY = TRIAL_FAMILY
    governor.CHANGED_VARIABLE = CHANGED_VARIABLE
    governor.RULE_VERSION = RULE_VERSION
    governor.TICKER_CLOSED_PROFIT_CAP_USD = TICKER_CLOSED_PROFIT_CAP_USD
    governor.TICKER_PROFIT_CAP_SCALAR = TICKER_PROFIT_CAP_SCALAR
    governor.GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD = GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD
    governor.GLOBAL_DRAWDOWN_SCALAR = GLOBAL_DRAWDOWN_SCALAR
    governor.GOVERNOR_AUDIT.clear()


def _round(value: Any, digits: int = 6) -> float | None:
    return _base()._round(value, digits)


def _aggregate_metrics(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev = sum(float(row.get("expected_value_score") or 0.0) for row in metrics_by_window.values())
    pnl = sum(float(row.get("total_pnl") or 0.0) for row in metrics_by_window.values())
    dd = max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics_by_window.values())
    trades = sum(int(row.get("trade_count") or 0) for row in metrics_by_window.values())
    return {
        "expected_value_score_sum": _round(ev, 6),
        "total_pnl_sum": _round(pnl, 2),
        "max_drawdown_pct_max": _round(dd, 6),
        "trade_count_sum": trades,
    }


def _comparison_vs_exp006(payload: dict[str, Any]) -> dict[str, Any]:
    if not REFERENCE_JSON.exists():
        return {"available": False, "reason": "missing_exp_20260528_006_reference"}
    reference = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))
    ref_after = reference.get("after_metrics") or {}
    after = payload.get("after_metrics") or {}
    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label in _base().WINDOWS:
        ref = ref_after.get(label) or {}
        cur = after.get(label) or {}
        by_window[label] = {
            "expected_value_score_delta": _round(
                float(cur.get("expected_value_score") or 0.0)
                - float(ref.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_delta": _round(
                float(cur.get("total_pnl") or 0.0) - float(ref.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_pct_delta": _round(
                float(cur.get("max_drawdown_pct") or 0.0)
                - float(ref.get("max_drawdown_pct") or 0.0),
                6,
            ),
        }
    ref_agg = _aggregate_metrics(ref_after)
    cur_agg = _aggregate_metrics(after)
    return {
        "available": True,
        "reference_experiment_id": "exp-20260528-006",
        "reference_decision": reference.get("decision"),
        "reference_gate4": reference.get("gate4"),
        "by_window_delta_after_vs_ungoverned_cash_conversion_quality": by_window,
        "aggregate_delta_after_vs_ungoverned_cash_conversion_quality": {
            "expected_value_score_delta_sum": _round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": _round(
                cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"],
                2,
            ),
            "max_drawdown_pct_delta_max": _round(
                cur_agg["max_drawdown_pct_max"] - ref_agg["max_drawdown_pct_max"],
                6,
            ),
        },
    }


def _build_payload() -> dict[str, Any]:
    base = _base()
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(base.get_universe())
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_day_counts: "OrderedDict[str, int]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = base.shadow._run_baseline(universe, cfg)
        before = base.overlay_helper._metrics(before_result)
        snapshot = base.shadow._load_snapshot(cfg["snapshot"])
        candidates = base._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        selected_trades, filtered_candidates = governor._select_governed_paper_trades(
            snapshot,
            candidates,
        )
        overlay = base._overlay_from_paper_trades(before_result, selected_trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = base.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        candidate_day_counts[label] = len({row["date"] for row in candidates})
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "raw_candidate_days": candidate_day_counts[label],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = base._aggregate(window_rows)
    target_summary = base._target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= base.MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= base.MAX_POSITIVE_HHI
    )
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(base.WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= base.MIN_TARGET_TRADES
        and len(target_windows) >= base.MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= base.MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )

    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < base.MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < base.MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > base.MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    decision = (
        "accepted_candidate_cash_conversion_closed_ledger_governor"
        if gate4_passed
        else "rejected_cash_conversion_closed_ledger_governor"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The cash-conversion Companyfacts+RS source had strong gross EV but failed "
            "drawdown and single-ticker concentration. Reusing the accepted "
            "closed-ledger governor may preserve the free-data candidate-pool alpha "
            "while making it promotion-safe."
        ),
        "change_type": "risk_allocation",
        "mechanism_family": "default_off_paper_risk_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": (
            "Apply the exp-20260528-008 closed paper-ledger governor to exp-20260528-006 "
            "cash-conversion candidates: if ticker closed PnL before entry is >= "
            f"${TICKER_CLOSED_PROFIT_CAP_USD:,.0f}, scale that ticker's later paper "
            f"notional to {TICKER_PROFIT_CAP_SCALAR:.2f}x; if sleeve closed-PnL "
            f"drawdown before entry is >= ${GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD:,.0f}, "
            f"scale paper notional to {GLOBAL_DRAWDOWN_SCALAR:.2f}x. Both use only "
            "exit_date < entry_date closed ledger rows."
        ),
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260528-006",
            "exp-20260528-008",
            "exp-20260528-017",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "reused_production_visible_closed_ledger_governor_on_distinct_companyfacts_source",
        "parameters": {
            "ticker_closed_profit_cap_usd": TICKER_CLOSED_PROFIT_CAP_USD,
            "ticker_profit_cap_scalar": TICKER_PROFIT_CAP_SCALAR,
            "global_closed_drawdown_trigger_usd": GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD,
            "global_drawdown_scalar": GLOBAL_DRAWDOWN_SCALAR,
            "source_experiment_id": "exp-20260528-006",
            "source_candidate_definition": (
                "PIT SEC operating_cash_flow/net_income cash conversion quality + "
                "Companyfacts growth + OHLCV RS"
            ),
            "locked_variables": [
                "all exp-20260528-006 cash-conversion source-quality fields",
                "all exp-20260527-017 Companyfacts growth thresholds",
                "all exp-20260527-017 RS proxy thresholds",
                "same-ticker cooldown disabled",
                "50d extension guard disabled",
                "sector exposure cap disabled",
                "QQQ confirmation disabled",
                "operating-profit quality disabled",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "watchlists",
                "live/default orders",
                "paper hold period",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / capital allocation alpha: a closed-ledger governor "
                "may turn cash-conversion candidate-pool alpha from gross-positive but "
                "unsafe into a promotion-safe default-off paper sleeve."
            ),
            "2_history_check": {
                "exp-20260528-006": (
                    "Cash-conversion source improved all windows with aggregate EV "
                    "+4.131 but failed drawdown/concentration."
                ),
                "exp-20260528-008": (
                    "The same closed-ledger governor made operating-profit quality pass "
                    "Gate 4 without live-order changes."
                ),
                "exp-20260528-017": (
                    "Low-liability support showed Companyfacts source-quality supports "
                    "can help the accepted fundamental stack."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
                "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
                "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
                "ticker concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260529_012_fundamental_cash_conversion_closed_ledger_governor.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "baseline_core_artifact": "data/experiments/exp-20260517-009/",
            "source_alpha_artifact": (
                "data/experiments/exp-20260528-006/"
                "fundamental_growth_rs_cash_conversion_quality.json"
            ),
            "paper_entry": "next available open from exp-20260528-006 source sleeve",
            "paper_exit": "10 trading days after signal from exp-20260528-006 source sleeve",
            "ledger_state_known_at": "closed paper rows with exit_date < entry_date",
        },
        "gate1": {
            "baseline_source": "docs/backtesting.md accepted core fixed-window metrics",
            "before_metrics": before_metrics,
        },
        "gate2": {
            "open_position_field_check": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
                "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                "SPY OHLCV Close rows for RS proxy",
                "PIT operating_cash_flow current comparable fact filed <= signal_date",
                "PIT net_income current comparable fact filed <= signal_date",
                "closed paper ledger rows with exit_date < entry_date",
            ],
            "new_fields": [
                "ticker_closed_pnl_before_entry",
                "global_closed_pnl_before_entry",
                "global_closed_drawdown_before_entry",
                "ticker_profit_cap_scalar",
                "global_drawdown_scalar",
            ],
            "passed": True,
            "note": (
                "SEC cash-flow and net-income rows are filtered by filed <= signal_date. "
                "The new governor depends only on closed paper ledger rows with "
                "exit_date < entry_date; production can expose the same state in a "
                "default-off shared sleeve before any activation."
            ),
        },
        "gate3": {
            "core_filter_added": False,
            "candidate_pool_changed": False,
            "survival_rate_min": _round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live entry rule was added. The governor scales "
                "default-off paper notional after candidate selection; core survival "
                "is unchanged."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "failed_checks": failed,
            "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_ev_regressed": aggregate["windows_ev_regressed"],
            "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
            "target_trade_count": target_summary["total_trade_count"],
            "target_trade_count_min": base.MIN_TARGET_TRADES,
            "target_windows": target_windows,
            "target_window_count_min": base.MIN_TARGET_WINDOWS,
            "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
            "max_drawdown_worse_guardrail": base.MAX_DRAWDOWN_WORSE,
            "survival_guard_passed": min_survival >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
                "max_single_positive_pnl_share_guardrail": base.MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": base.MAX_POSITIVE_HHI,
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, window_rows[label]["delta"]) for label in base.WINDOWS
            ),
            "aggregate": aggregate,
        },
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_day_counts": candidate_day_counts,
        "cash_conversion_quality_audit": source.CASH_QUALITY_AUDIT,
        "fundamental_growth_rs_audit": source.prev.FUNDAMENTAL_RS_AUDIT,
        "closed_ledger_governor_audit": governor.GOVERNOR_AUDIT,
        "comparison_vs_exp006": {},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "default_off_paper_only": True,
            "replay_only": True,
            "trade_enabled": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "Gate 4 passing evidence is not live activation. Promotion requires "
                "moving this governor into a shared default-off paper adapter, exposing "
                "the same closed-ledger state in daily run artifacts, adding parity "
                "tests, and then running a dedicated activation experiment."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking, expectation revision, and Kova intraday because "
            "recent records show sparse or readiness-blocked attribution. Skipped "
            "VCP, VBB, state-surface, broad-market, and nearby Companyfacts growth, "
            "RS, top-N, cooldown, extension, QQQ, sector-exposure, and scalar retunes "
            "per playbook freeze guidance. This run reuses a previously accepted "
            "production-visible governor on a distinct free Companyfacts source."
        ),
        "interpretation": (
            "Gate 4 passed. The cash-conversion source remains economically useful "
            "after closed-ledger governance, while drawdown and ticker concentration "
            "move inside the promotion-readiness guardrails. This is a candidate for "
            "a shared default-off paper adapter, not an immediate live order change."
            if gate4_passed
            else (
                "Gate 4 failed. Do not promote this governor on the cash-conversion "
                "source; require forward rows or a materially new free-data source "
                "before retrying nearby Companyfacts+RS cash-flow threshold variants."
            )
        ),
        "next_evidence_needed": (
            "If accepted, implement the same governor in a shared default-off paper "
            "sleeve with production daily report exposure and parity tests; then "
            "collect forward closed outcomes before enabling any live capital."
        ),
        "anti_js": {"javascript_used": False},
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
        ],
    }
    payload["comparison_vs_exp006"] = _comparison_vs_exp006(payload)
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260529-012 Cash-Conversion Closed-Ledger Governor",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: apply the accepted closed-paper-ledger profit-cap and "
            "drawdown governor to the exp-20260528-006 cash-conversion Companyfacts+RS "
            "default-off paper sleeve."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Profit-cap scaled | DD scaled |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _base().WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["closed_ledger_governor_audit"].get(label, {})
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {profit_scaled} | {dd_scaled} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                profit_scaled=audit.get("ticker_profit_cap_scaled", 0),
                dd_scaled=audit.get("global_drawdown_scaled", 0),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    target = payload["target_trade_summary"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{aggregate['target_trade_count_sum']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Governor Audit",
            "",
            "```json",
            json.dumps(payload["closed_ledger_governor_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Comparison With exp-20260528-006",
            "",
            "```json",
            json.dumps(payload["comparison_vs_exp006"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Experiment-only default-off paper evidence. No shared policy, run "
                "adapter, backtester adapter, production watchlist, live/default order "
                "path, core entry, ranking, sizing, or exit behavior changed. A "
                "production promotion would need this exact closed-ledger state and "
                "governor in a shared adapter plus parity tests."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _persist(payload: dict[str, Any]) -> None:
    base = _base()
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Cash-conversion closed-ledger governor",
        "status": payload["decision"],
        "lane": "alpha_search",
        "updated_at": payload["timestamp"],
        "artifacts": {
            "json": base._repo_rel(OUT_JSON),
            "log": base._repo_rel(LOG_JSON),
            "report": base._repo_rel(ARTIFACT_MD),
        },
    }
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, ticket)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
