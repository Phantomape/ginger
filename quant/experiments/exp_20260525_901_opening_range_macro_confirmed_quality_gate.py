"""exp-20260525-901: opening-range macro-confirmed quality gate.

This alpha search follows the rejected opening-range paper sleeve family from
exp-20260525-011 and exp-20260525-012. The single tested variable is an
orthogonal free-data macro confirmation field on the already selected
non-Tech/orderly daily top-1 opening-range paper candidate:

- SPY 20-day return is above TLT 20-day return; and
- SPY 20-day return is above UUP 20-day return.

The gate is tested as default-off paper only. Core entries, ranking, sizing,
exits, heat, LLM/news replay, watchlists, and live/default orders are unchanged.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as prior
import exp_20260525_012_opening_range_nontech_orderly_quality_gate as quality


EXPERIMENT_ID = "exp-20260525-901"
STEM = "opening_range_macro_confirmed_quality_gate"
TRIAL_FAMILY = "opening_range_continuation_macro_confirmed_paper_sleeve"
CHANGED_VARIABLE = "opening_range_top1_nontech_orderly_macro_confirmation_v1"

LOOKBACK_DAYS = 20
MACRO_CONFIRMATION_ASSETS = ("TLT", "UUP")

MIN_TARGET_TRADES = 45
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.35
MAX_POSITIVE_HHI = 0.25

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
WINDOWS = prior.WINDOWS


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _series_return(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date: str,
    lookback: int,
) -> float | None:
    rows = prior.shadow._series(snapshot, ticker)
    index = prior.shadow._row_index(rows).get(date)
    if index is None or index < lookback:
        return None
    current = prior.shadow._value(rows[index], "Close")
    prior_close = prior.shadow._value(rows[index - lookback], "Close")
    if not current or not prior_close:
        return None
    return (current / prior_close) - 1.0


def _macro_confirmation(
    snapshot: dict[str, list[dict[str, Any]]],
    date: str,
) -> tuple[bool, str, dict[str, Any]]:
    spy_ret = _series_return(snapshot, "SPY", date, LOOKBACK_DAYS)
    asset_returns = {
        ticker: _series_return(snapshot, ticker, date, LOOKBACK_DAYS)
        for ticker in MACRO_CONFIRMATION_ASSETS
    }
    metrics: dict[str, Any] = {
        "lookback_days": LOOKBACK_DAYS,
        "spy_return_20": _round(spy_ret, 6),
        "macro_asset_returns_20": {
            ticker: _round(value, 6) for ticker, value in asset_returns.items()
        },
    }
    if spy_ret is None:
        return False, "missing_spy_macro_return", metrics
    missing = [ticker for ticker, value in asset_returns.items() if value is None]
    if missing:
        metrics["missing_assets"] = missing
        return False, "missing_macro_asset_return", metrics
    if any(spy_ret <= float(value) for value in asset_returns.values()):
        return False, "macro_risk_appetite_not_confirmed", metrics
    return True, "passed_equity_vs_bond_usd_macro_confirmation", metrics


def _select_macro_confirmed_top1(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    quality_selected, quality_rejected, original_filtered = (
        quality._select_quality_gated_top1(snapshot, candidates)
    )
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for trade in quality_selected:
        date = str(trade.get("date") or trade.get("signal_date") or "")
        passed, reason, metrics = _macro_confirmation(snapshot, date)
        enriched = {
            **trade,
            "macro_confirmation_reason": reason,
            "macro_confirmation": metrics,
        }
        if passed:
            selected.append(enriched)
        else:
            rejected.append(enriched)
    return selected, rejected, original_filtered


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": _round(ev_before, 6),
        "after_expected_value_score_sum": _round(ev_after, 6),
        "expected_value_score_delta_sum": _round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": _round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": _round(pnl_before, 2),
        "after_total_pnl_sum": _round(pnl_after, 2),
        "total_pnl_delta_sum": _round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": _round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = prior._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(prior.get_universe())
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    macro_rejected_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    original_filtered_sample_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    quality_top1_counts: "OrderedDict[str, int]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = prior.shadow._run_baseline(universe, cfg)
        before = prior.overlay_helper._metrics(before_result)
        snapshot = prior.shadow._load_snapshot(cfg["snapshot"])
        candidates = prior._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        selected_trades, macro_rejected, original_filtered = _select_macro_confirmed_top1(
            snapshot,
            candidates,
        )
        overlay = prior._overlay_from_paper_trades(before_result, selected_trades)
        after = prior.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = prior.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        macro_rejected_by_window[label] = macro_rejected[:200]
        original_filtered_sample_by_window[label] = original_filtered[:100]
        raw_candidate_counts[label] = len(candidates)
        quality_top1_counts[label] = len(selected_trades) + len(macro_rejected)
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "macro_rejected_count": len(macro_rejected),
            "quality_top1_count": quality_top1_counts[label],
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
        }

    aggregate = _aggregate(window_rows)
    target_summary = prior._target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )

    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_improved"] != len(WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    decision = (
        "promising_replay_only_opening_range_macro_confirmed_quality_gate"
        if gate4_passed
        else "rejected_opening_range_macro_confirmed_quality_gate"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The rejected opening-range continuation paper source may need an "
            "orthogonal macro risk-appetite confirmation rather than another "
            "local price threshold. A daily top-1 non-Tech/orderly candidate "
            "should have better replacement value when equities have outperformed "
            "both long-duration Treasuries and the dollar over the prior 20 "
            "trading days."
        ),
        "change_type": "opening_range_continuation_macro_confirmed_paper_sleeve",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260525-011",
            "exp-20260525-012",
            "exp-20260426-041",
            "exp-20260426-045",
            "exp-20260426-051",
            "exp-20260426-062",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "orthogonal_cross_asset_macro_confirmation_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Same as exp-20260525-011/012: signal uses same-day/prior-day "
                "OHLCV; paper entry is next available open with production entry "
                "slippage; exit is the close ten trading days after the signal "
                "with sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "base_universe_count": len(universe),
            "paper_notional_usd": prior.BASE_NOTIONAL_USD,
            "hold_days": prior.HOLD_DAYS,
            "macro_confirmation": {
                "lookback_days": LOOKBACK_DAYS,
                "condition": "SPY_20d_return > TLT_20d_return and SPY_20d_return > UUP_20d_return",
                "assets": ["SPY", *MACRO_CONFIRMATION_ASSETS],
            },
            "base_quality_gate": {
                "applies_after_original_daily_top1_selection": True,
                "excluded_sector": quality.EXCLUDED_SECTOR,
                "candidate_day_return_gt": 0.0,
                "candidate_day_return_lte": quality.MAX_CANDIDATE_DAY_RETURN,
                "open_vs_prior_close_lte": quality.MAX_OPEN_VS_PRIOR_CLOSE,
            },
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "opening-range raw candidate formula",
                "daily top-1 ranking order",
                "base quality gate",
                "paper notional",
                "paper hold period",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: a free cross-asset macro confirmation "
                "field may improve the opening-range paper source by avoiding "
                "risk-off continuation traps."
            ),
            "2_history_check": {
                "exp-20260525-011": (
                    "Raw opening-range top-1 fixed-notional sleeve improved "
                    "aggregate EV/PnL but failed late_strong and drawdown."
                ),
                "exp-20260525-012": (
                    "Non-Tech orderly gate improved all three windows but missed "
                    "the drawdown guard by 0.09 percentage points; its next valid "
                    "retry required a materially different source/event "
                    "confirmation field. This run supplies a cross-asset macro "
                    "confirmation field."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                "3/3 EV-improved windows; no EV/PnL-regressed window; >=45 paper "
                "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                ">=5%; concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260525_901_opening_range_macro_confirmed_quality_gate.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Close/Volume rows",
                "SPY/TLT/UUP OHLCV rows for same-window macro confirmation",
                "candidate sector emitted by opening-range candidate builder",
                "candidate_day_return",
                "open_vs_prior_close",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or core entry rule was added. The target source "
                "is evaluated as additive default-off paper, so core survival is "
                "unchanged from the baseline replay."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
            "windows_ev_improved": aggregate["windows_ev_improved"],
            "windows_ev_regressed": aggregate["windows_ev_regressed"],
            "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
            "target_trade_count": target_summary["total_trade_count"],
            "target_trade_count_min": MIN_TARGET_TRADES,
            "target_windows": target_windows,
            "target_window_count_min": MIN_TARGET_WINDOWS,
            "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
            "survival_guard_passed": min_survival >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary[
                    "max_single_positive_pnl_share"
                ],
                "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
                "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
                "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "raw_candidate_counts": raw_candidate_counts,
        "quality_top1_counts": quality_top1_counts,
        "target_trades_by_window": target_trades_by_window,
        "macro_rejected_by_window": macro_rejected_by_window,
        "original_filtered_sample_by_window": original_filtered_sample_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result would still require a shared default-off paper "
                "adapter, daily report exposure, forward replacement-value ledger, "
                "and parity tests before any live/default behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because replay-safe attribution remains sparse; "
            "skipped AI/compute/consumer/Space fixed-notional retreads due recent "
            "anti-repeat gates; skipped nearby opening-range local OHLCV gates after "
            "exp-20260525-012. This tests a materially different cross-asset macro "
            "confirmation field using free OHLCV data."
        ),
        "interpretation": (
            "The macro-confirmed opening-range quality gate cleared replay-only "
            "Gate 4. This is a research lead only; no production/shared policy was "
            "promoted."
            if gate4_passed
            else (
                "The macro-confirmed opening-range quality gate did not clear Gate "
                "4. Do not retry nearby opening-range gates on the frozen sample "
                "without forward paper rows or a genuinely new non-price source."
            )
        ),
        "rejection_reason": None if gate4_passed else "; ".join(failed),
        "next_evidence_needed": (
            "If retained, build forward default-off opening-range paper rows and "
            "replacement-value reporting before any shared adapter or live sleeve "
            "activation."
            if gate4_passed
            else (
                "Forward opening-range paper rows or a genuinely new non-price "
                "source confirmation."
            )
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target | Macro rejected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {rejected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                rejected=len(payload["macro_rejected_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Opening-Range Macro-Confirmed Quality Gate",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the existing non-Tech/orderly opening-range daily top-1 source into default-off paper only when SPY has outperformed both TLT and UUP over the prior 20 trading days.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- changed_variable: `{payload['changed_variable']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Opening-range macro-confirmed quality gate",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
