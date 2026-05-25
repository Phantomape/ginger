"""exp-20260525-028: opening-range sector-leadership quality gate.

This alpha search follows the rejected opening-range paper sleeve family from
exp-20260525-011, exp-20260525-012, and exp-20260525-901. The single tested
variable is an orthogonal free-OHLCV sector confirmation field on the already
selected non-Tech/orderly daily top-1 opening-range paper candidate:

- candidate sector must be one of the top three 20-day sector-median leaders;
- that sector median 20-day return must exceed SPY's 20-day return.

The gate is tested as default-off paper only. Core entries, ranking, sizing,
exits, heat, LLM/news replay, watchlists, and live/default orders are unchanged.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_sector_leadership_trend_shadow as sector_shadow  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as prior  # noqa: E402
import exp_20260525_012_opening_range_nontech_orderly_quality_gate as quality  # noqa: E402


EXPERIMENT_ID = "exp-20260525-028"
STEM = "opening_range_sector_leadership_quality_gate"
TRIAL_FAMILY = "opening_range_continuation_sector_leadership_paper_sleeve"
CHANGED_VARIABLE = "opening_range_top1_nontech_orderly_sector_leadership_v1"

LOOKBACK_DAYS = 20

MIN_TARGET_TRADES = 45
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.35
MAX_POSITIVE_HHI = 0.25

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


def _spy_return_20(
    snapshot: dict[str, list[dict[str, Any]]],
    date: str,
) -> float | None:
    rows = prior.shadow._series(snapshot, "SPY")
    idx = prior.shadow._row_index(rows).get(date)
    if idx is None:
        return None
    return sector_shadow._return_from_closes(rows, idx - LOOKBACK_DAYS, idx)


def _sector_confirmation(
    snapshot: dict[str, list[dict[str, Any]]],
    sector_state_by_date: dict[str, dict[str, Any]],
    trade: dict[str, Any],
) -> tuple[bool, str, dict[str, Any]]:
    date = str(trade.get("date") or trade.get("signal_date") or "")
    sector = str(trade.get("sector") or "Unknown")
    state = sector_state_by_date.get(date) or {}
    leader_ranks = state.get("leader_ranks") or {}
    sector_medians = state.get("sector_medians") or {}
    sector_rank = leader_ranks.get(sector)
    sector_return = sector_medians.get(sector)
    spy_return = _spy_return_20(snapshot, date)
    metrics = {
        "lookback_days": LOOKBACK_DAYS,
        "sector": sector,
        "sector_rank_20d": sector_rank,
        "sector_median_20d_return": _round(sector_return, 6),
        "spy_20d_return": _round(spy_return, 6),
        "sector_minus_spy_20d": _round(sector_return - spy_return, 6)
        if isinstance(sector_return, (int, float)) and isinstance(spy_return, (int, float))
        else None,
    }
    if sector_rank is None:
        return False, "sector_not_top3_leader", metrics
    if sector_return is None:
        return False, "missing_sector_median_return", metrics
    if spy_return is None:
        return False, "missing_spy_return", metrics
    if sector_return <= spy_return:
        return False, "sector_not_leading_spy", metrics
    return True, "passed_sector_leadership_confirmation", metrics


def _select_sector_confirmed_top1(
    snapshot: dict[str, list[dict[str, Any]]],
    universe: list[str],
    cfg: dict[str, str],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    dates = [
        date
        for date in prior.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    sector_state_by_date = sector_shadow._sector_daily_returns(snapshot, universe, dates)
    quality_selected, quality_rejected, original_filtered = (
        quality._select_quality_gated_top1(snapshot, candidates)
    )
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for trade in quality_selected:
        passed, reason, metrics = _sector_confirmation(
            snapshot,
            sector_state_by_date,
            trade,
        )
        enriched = {
            **trade,
            "sector_confirmation_reason": reason,
            "sector_confirmation": metrics,
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
    sector_rejected_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    original_filtered_sample_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    quality_top1_counts: "OrderedDict[str, int]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = prior.shadow._run_baseline(universe, cfg)
        before = prior.overlay_helper._metrics(before_result)
        snapshot = prior.shadow._load_snapshot(cfg["snapshot"])
        candidates = prior._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        selected_trades, sector_rejected, original_filtered = _select_sector_confirmed_top1(
            snapshot,
            universe,
            cfg,
            candidates,
        )
        overlay = prior._overlay_from_paper_trades(before_result, selected_trades)
        after = prior.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = prior.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        sector_rejected_by_window[label] = sector_rejected[:200]
        original_filtered_sample_by_window[label] = original_filtered[:100]
        raw_candidate_counts[label] = len(candidates)
        quality_top1_counts[label] = len(selected_trades) + len(sector_rejected)
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "sector_rejected_count": len(sector_rejected),
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
        "promising_replay_only_opening_range_sector_leadership_quality_gate"
        if gate4_passed
        else "rejected_opening_range_sector_leadership_quality_gate"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The non-Tech/orderly opening-range source may need sector-level "
            "breadth support rather than another local price threshold. A daily "
            "top-1 candidate should have better replacement value when its sector "
            "is a top-three 20-day median-return leader and is also beating SPY."
        ),
        "change_type": "opening_range_continuation_sector_confirmed_paper_sleeve",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260525-011",
            "exp-20260525-012",
            "exp-20260525-901",
            "exp-20260426-041",
            "exp-20260426-049",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "orthogonal_sector_median_leadership_confirmation_field",
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
            "sector_confirmation": {
                "lookback_days": LOOKBACK_DAYS,
                "condition": (
                    "candidate sector rank by 20d median return <= 3 and "
                    "candidate sector median 20d return > SPY 20d return"
                ),
                "source": "canonical OHLCV snapshot Close values",
                "known_at": "after signal-date close, before next-open paper entry",
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
                "entry / candidate_pool: free-OHLCV sector breadth confirmation "
                "may improve opening-range paper candidates by avoiding isolated "
                "single-stock continuations in weak sectors."
            ),
            "2_history_check": {
                "exp-20260525-011": (
                    "Raw opening-range top-1 fixed-notional sleeve improved "
                    "aggregate EV/PnL but failed late_strong and drawdown."
                ),
                "exp-20260525-012": (
                    "Non-Tech orderly gate improved all three windows but missed "
                    "the drawdown guard by 0.09 percentage points."
                ),
                "exp-20260525-901": (
                    "Cross-asset macro confirmation did not solve the family; it "
                    "kept EV positive but introduced a mid_weak PnL regression. "
                    "This run uses sector-median breadth, not macro confirmation."
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
                "exp_20260525_028_opening_range_sector_leadership_quality_gate.py"
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
                "SPY OHLCV rows for same-window relative strength",
                "sector median 20d return computed from same-day core universe OHLCV",
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
        "sector_rejected_by_window": sector_rejected_by_window,
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
            "anti-repeat gates; skipped nearby opening-range local OHLCV and macro "
            "gates after exp-20260525-012/901. This tests a materially different "
            "sector breadth field using free OHLCV data."
        ),
        "interpretation": (
            "The sector-confirmed opening-range quality gate cleared replay-only "
            "Gate 4. This is a research lead only; no production/shared policy was "
            "promoted."
            if gate4_passed
            else (
                "The sector-confirmed opening-range quality gate did not clear Gate "
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target | Sector rejected |",
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
                rejected=len(payload["sector_rejected_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Opening-Range Sector-Leadership Quality Gate",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the existing non-Tech/orderly opening-range daily top-1 source into default-off paper only when its sector is a top-three 20d sector-median leader and is beating SPY.",
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
            "title": "Opening-range sector-leadership quality gate",
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
