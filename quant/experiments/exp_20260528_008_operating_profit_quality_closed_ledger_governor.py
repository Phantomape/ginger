"""exp-20260528-008: operating-profit quality closed-ledger governor.

Alpha search follow-up to exp-20260528-004. This keeps the PIT SEC
Companyfacts operating-profit + OHLCV RS candidate source fixed, then changes
one launch-readiness variable: a production-visible closed-paper-ledger
governor that scales later sleeve notional when a ticker has already
contributed enough closed PnL or the sleeve has entered closed-PnL drawdown.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_004_fundamental_growth_rs_operating_profit_quality as source


EXPERIMENT_ID = "exp-20260528-008"
STEM = "operating_profit_quality_closed_ledger_governor"
TRIAL_FAMILY = "fundamental_growth_rs_operating_profit_quality_launch_governor"
CHANGED_VARIABLE = "operating_profit_quality_closed_ledger_profit_cap_drawdown_governor_v1"
RULE_VERSION = "operating_profit_quality_closed_ledger_governor_v1"

TICKER_CLOSED_PROFIT_CAP_USD = 9_000.0
TICKER_PROFIT_CAP_SCALAR = 0.05
GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD = 7_500.0
GLOBAL_DRAWDOWN_SCALAR = 0.25

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REFERENCE_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260528-004.json"

GOVERNOR_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    source._configure_modules()


def _round(value: Any, digits: int = 6) -> float | None:
    return _base()._round(value, digits)


def _window_label_for_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "unknown"
    dates = [str(row.get("date") or "") for row in candidates if row.get("date")]
    if not dates:
        return "unknown"
    first = min(dates)
    last = max(dates)
    for label, cfg in _base().WINDOWS.items():
        if str(cfg["start"]) <= first and last <= str(cfg["end"]):
            return label
    return "unknown"


def _update_closed_state(
    pending_closes: list[dict[str, Any]],
    entry_date: str,
    cumulative_closed_pnl: float,
    peak_closed_pnl: float,
    ticker_closed_pnl: dict[str, float],
) -> tuple[list[dict[str, Any]], float, float, float]:
    remaining: list[dict[str, Any]] = []
    max_closed_drawdown = 0.0
    due: list[dict[str, Any]] = []
    for item in pending_closes:
        if str(item["exit_date"]) < entry_date:
            due.append(item)
        else:
            remaining.append(item)
    for item in sorted(due, key=lambda row: str(row["exit_date"])):
        pnl = float(item.get("pnl") or 0.0)
        ticker = str(item.get("ticker") or "").upper()
        cumulative_closed_pnl += pnl
        peak_closed_pnl = max(peak_closed_pnl, cumulative_closed_pnl)
        max_closed_drawdown = max(max_closed_drawdown, peak_closed_pnl - cumulative_closed_pnl)
        ticker_closed_pnl[ticker] += pnl
    return remaining, cumulative_closed_pnl, peak_closed_pnl, max_closed_drawdown


def _select_governed_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = _base()
    label = _window_label_for_candidates(candidates)
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    pending_closes: list[dict[str, Any]] = []
    ticker_closed_pnl: defaultdict[str, float] = defaultdict(float)
    cumulative_closed_pnl = 0.0
    peak_closed_pnl = 0.0
    max_closed_drawdown_seen = 0.0
    audit: Counter[str] = Counter()
    scaled_ticker_counts: Counter[str] = Counter()

    for row in candidates:
        date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        if row.get("same_ticker_ab_overlap"):
            audit["same_ticker_core_overlap_filtered"] += 1
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= base.MAX_PAPER_TRADES_PER_DAY:
            audit["daily_top1_filtered"] += 1
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue

        trade = base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            audit["missing_trade_filtered"] += 1
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue

        entry_date = str(trade.get("entry_date") or date)
        pending_closes, cumulative_closed_pnl, peak_closed_pnl, latest_dd = _update_closed_state(
            pending_closes,
            entry_date,
            cumulative_closed_pnl,
            peak_closed_pnl,
            ticker_closed_pnl,
        )
        max_closed_drawdown_seen = max(max_closed_drawdown_seen, latest_dd)
        closed_drawdown = peak_closed_pnl - cumulative_closed_pnl

        ticker_profit_scalar = (
            TICKER_PROFIT_CAP_SCALAR
            if ticker_closed_pnl[ticker] >= TICKER_CLOSED_PROFIT_CAP_USD
            else 1.0
        )
        global_drawdown_scalar = (
            GLOBAL_DRAWDOWN_SCALAR
            if closed_drawdown >= GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD
            else 1.0
        )
        notional_scalar = ticker_profit_scalar * global_drawdown_scalar
        if ticker_profit_scalar < 1.0:
            audit["ticker_profit_cap_scaled"] += 1
            scaled_ticker_counts[ticker] += 1
        if global_drawdown_scalar < 1.0:
            audit["global_drawdown_scaled"] += 1
        if ticker_profit_scalar < 1.0 and global_drawdown_scalar < 1.0:
            audit["both_scalars_applied"] += 1

        base_notional = float(trade.get("paper_notional_usd") or base.BASE_NOTIONAL_USD)
        pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
        governed_notional = base_notional * notional_scalar
        governed_pnl = governed_notional * pnl_pct_net
        governed_trade = {
            **trade,
            "closed_ledger_governor_rule_version": RULE_VERSION,
            "closed_ledger_governor_trade_enabled": False,
            "closed_ledger_governor_alters_orders": False,
            "closed_ledger_governor_known_at": "closed paper ledger rows with exit_date < entry_date",
            "ticker_closed_profit_cap_usd": TICKER_CLOSED_PROFIT_CAP_USD,
            "ticker_profit_cap_scalar": ticker_profit_scalar,
            "global_closed_drawdown_trigger_usd": GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD,
            "global_drawdown_scalar": global_drawdown_scalar,
            "closed_ledger_notional_scalar": _round(notional_scalar, 6),
            "global_closed_pnl_before_entry": _round(cumulative_closed_pnl, 2),
            "global_closed_peak_pnl_before_entry": _round(peak_closed_pnl, 2),
            "global_closed_drawdown_before_entry": _round(closed_drawdown, 2),
            "ticker_closed_pnl_before_entry": _round(ticker_closed_pnl[ticker], 2),
            "paper_notional_usd": _round(governed_notional, 2),
            "pnl": _round(governed_pnl, 2),
            "selection_rule_version": RULE_VERSION,
            "rule_version": RULE_VERSION,
        }
        selected.append(governed_trade)
        used_date_counts[date] += 1
        pending_closes.append(
            {
                "ticker": ticker,
                "exit_date": str(governed_trade.get("exit_date") or ""),
                "pnl": float(governed_trade.get("pnl") or 0.0),
            }
        )
        audit["selected_trades"] += 1

    # Flush for diagnostics only; decisions above never see these future closes.
    for item in sorted(pending_closes, key=lambda row: str(row["exit_date"])):
        pnl = float(item.get("pnl") or 0.0)
        cumulative_closed_pnl += pnl
        peak_closed_pnl = max(peak_closed_pnl, cumulative_closed_pnl)
        max_closed_drawdown_seen = max(max_closed_drawdown_seen, peak_closed_pnl - cumulative_closed_pnl)

    GOVERNOR_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "ticker_closed_profit_cap_usd": TICKER_CLOSED_PROFIT_CAP_USD,
        "ticker_profit_cap_scalar": TICKER_PROFIT_CAP_SCALAR,
        "global_closed_drawdown_trigger_usd": GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD,
        "global_drawdown_scalar": GLOBAL_DRAWDOWN_SCALAR,
        "input_candidates": len(candidates),
        "selected_trades": len(selected),
        "filtered_candidates": len(filtered),
        "final_closed_pnl": _round(cumulative_closed_pnl, 2),
        "max_closed_drawdown_seen_usd": _round(max_closed_drawdown_seen, 2),
        "selected_unique_tickers": len({str(row.get("ticker") or "").upper() for row in selected}),
        "selected_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in selected).items())
        ),
        "scaled_ticker_counts": dict(sorted(scaled_ticker_counts.items())),
        **dict(sorted(audit.items())),
    }
    return selected, filtered


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


def _comparison_vs_exp004(payload: dict[str, Any]) -> dict[str, Any]:
    if not REFERENCE_JSON.exists():
        return {"available": False, "reason": "missing_exp_20260528_004_reference"}
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
        "reference_experiment_id": "exp-20260528-004",
        "reference_decision": reference.get("decision"),
        "reference_gate4": reference.get("gate4"),
        "by_window_delta_after_vs_ungoverned_operating_profit_quality": by_window,
        "aggregate_delta_after_vs_ungoverned_operating_profit_quality": {
            "expected_value_score_delta_sum": _round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": _round(
                cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"], 2
            ),
            "max_drawdown_pct_delta_max": _round(
                cur_agg["max_drawdown_pct_max"] - ref_agg["max_drawdown_pct_max"], 6
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
        selected_trades, filtered_candidates = _select_governed_paper_trades(snapshot, candidates)
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
        "accepted_candidate_operating_profit_quality_closed_ledger_governor"
        if gate4_passed
        else "rejected_operating_profit_quality_closed_ledger_governor"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The operating-profit Companyfacts+RS sleeve is high-EV but unsafe "
            "because closed winners and drawdown concentrate in a few tickers. A "
            "production-visible closed-ledger governor can preserve most EV while "
            "keeping drawdown and single-ticker contribution within Gate 4 bounds."
        ),
        "change_type": "risk_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": (
            "Closed paper-ledger launch governor: if ticker closed PnL before entry "
            f"is >= ${TICKER_CLOSED_PROFIT_CAP_USD:,.0f}, scale that ticker's later "
            f"paper notional to {TICKER_PROFIT_CAP_SCALAR:.2f}x; if sleeve closed-PnL "
            f"drawdown before entry is >= ${GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD:,.0f}, "
            f"scale paper notional to {GLOBAL_DRAWDOWN_SCALAR:.2f}x. Both conditions "
            "use only exit_date < entry_date closed ledger rows."
        ),
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "parameters": {
            "ticker_closed_profit_cap_usd": TICKER_CLOSED_PROFIT_CAP_USD,
            "ticker_profit_cap_scalar": TICKER_PROFIT_CAP_SCALAR,
            "global_closed_drawdown_trigger_usd": GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD,
            "global_drawdown_scalar": GLOBAL_DRAWDOWN_SCALAR,
            "source_experiment_id": "exp-20260528-004",
            "source_candidate_definition": "PIT positive quarterly operating income + Companyfacts growth + OHLCV RS",
        },
        "gate_questions": {
            "alpha_hypothesis": (
                "risk allocation / capital allocation: closed-ledger contribution and "
                "drawdown governance may make the strong operating-profit quality sleeve "
                "promotion-safe without changing its entry signal."
            ),
            "prior_similar_experiments": [
                "exp-20260528-004: strong EV/PnL, rejected for old_thin drawdown and APP concentration.",
                "exp-20260527-018: ticker cooldown reduced concentration but regressed one window.",
                "exp-20260527-903: sector exposure cap improved economics but failed drawdown.",
            ],
            "independent_variable": CHANGED_VARIABLE,
            "acceptance_standard": (
                "docs/backtesting.md canonical three windows; aggregate EV/PnL positive; "
                "3/3 EV windows improve; no PnL-regressed window; target trades >=30 "
                "across all 3 windows; max drawdown drift <=0.5pp; survival >=5%; "
                "ticker positive-PnL share <=40% and positive-PnL HHI <=0.30."
            ),
            "reproducibility": (
                "Run .\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260528_008_operating_profit_quality_closed_ledger_governor.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "baseline_core_artifact": "data/experiments/exp-20260517-009/",
            "source_alpha_artifact": "data/experiments/exp-20260528-004/fundamental_growth_rs_operating_profit_quality.json",
            "paper_entry": "next available open from exp-20260528-004 source sleeve",
            "paper_exit": "10 trading days after signal from exp-20260528-004 source sleeve",
            "ledger_state_known_at": "closed paper rows with exit_date < entry_date",
        },
        "gate1": {
            "baseline_source": "docs/backtesting.md accepted core fixed-window metrics",
            "before_metrics": before_metrics,
        },
        "gate2": {
            "open_position_field_check": gate2_open_positions,
            "new_fields": [
                "ticker_closed_pnl_before_entry",
                "global_closed_pnl_before_entry",
                "global_closed_drawdown_before_entry",
                "ticker_profit_cap_scalar",
                "global_drawdown_scalar",
            ],
            "passed": True,
            "note": (
                "Companyfacts and OHLCV source fields remain PIT as in exp-20260528-004. "
                "The new governor depends only on closed paper ledger rows with "
                "exit_date < entry_date, which production can expose from the same "
                "default-off ledger."
            ),
        },
        "gate3": {
            "core_filter_added": False,
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
        "operating_profit_quality_audit": source.OPERATING_QUALITY_AUDIT,
        "closed_ledger_governor_audit": GOVERNOR_AUDIT,
        "comparison_vs_exp004": {},
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
            "Did not change the operating-profit quality signal, Companyfacts fields, "
            "RS proxy, top-N candidate definition, exit horizon, live/core sizing, or "
            "LLM/news path. Prior probes showed hard ticker cooldown/open caps were "
            "too blunt; this run tests a closed-ledger launch governor because it "
            "directly targets the exp-20260528-004 drawdown and concentration blockers."
        ),
        "interpretation": (
            "Gate 4 passed. The operating-profit quality alpha remains economically "
            "strong after a closed-ledger governor, while drawdown and ticker "
            "concentration move inside the promotion-readiness guardrails. This is a "
            "candidate for a shared default-off paper adapter, not an immediate live "
            "order change."
            if gate4_passed
            else (
                "Gate 4 failed. Do not promote this governor; use the artifact to "
                "choose the next risk-control hypothesis."
            )
        ),
        "next_evidence_needed": (
            "Implement the same governor in a shared default-off paper sleeve with "
            "production daily report exposure and parity tests; then collect forward "
            "closed outcomes before enabling any live capital."
        ),
        "anti_js": {"javascript_used": False},
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(DOC_TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
        ],
    }
    payload["comparison_vs_exp004"] = _comparison_vs_exp004(payload)
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260528-008 Operating-Profit Closed-Ledger Governor",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: apply a production-visible closed-paper-ledger governor "
            "to the exp-20260528-004 operating-profit quality sleeve."
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
        "title": "Operating-profit quality closed-ledger governor",
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
    base._write_json(DOC_TICKET_JSON, ticket)
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
