"""exp-20260528-020: Companyfacts+RS dual-growth support.

Alpha search follow-up to the accepted Companyfacts operating-profit + RS
paper lead, low-volume support, filing-recency support, and low-liability
support. This keeps the accepted candidate source, daily top-1 selection,
10-day hold, closed-ledger governor, and all prior paper-notional supports
fixed. It changes one production-visible free SEC field: support selected
paper candidates whose PIT revenue and EPS growth checks both pass.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260528_017_fundamental_growth_rs_low_liability_support as prev


EXPERIMENT_ID = "exp-20260528-020"
STEM = "fundamental_growth_rs_dual_growth_support"
TRIAL_FAMILY = "fundamental_growth_rs_dual_growth_support"
CHANGED_VARIABLE = "fundamental_growth_rs_dual_growth_notional_scalar_v1"
RULE_VERSION = "fundamental_growth_rs_dual_growth_support_v1"

DUAL_GROWTH_NOTIONAL_SCALAR = 1.05

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

DUAL_GROWTH_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _base():
    return prev._base()


def _source_base():
    return prev._source_base()


def _governor():
    return prev._governor()


def _configure_modules() -> None:
    prev.EXPERIMENT_ID = EXPERIMENT_ID
    prev.STEM = STEM
    prev.TRIAL_FAMILY = TRIAL_FAMILY
    prev.CHANGED_VARIABLE = CHANGED_VARIABLE
    prev.RULE_VERSION = RULE_VERSION
    prev.OUT_DIR = OUT_DIR
    prev.OUT_JSON = OUT_JSON
    prev.LOG_JSON = LOG_JSON
    prev.TICKET_JSON = TICKET_JSON
    prev.DOC_TICKET_JSON = DOC_TICKET_JSON
    prev.ARTIFACT_MD = ARTIFACT_MD
    prev.EXPERIMENT_LOG = EXPERIMENT_LOG
    prev.BALANCE_SHEET_AUDIT.clear()
    DUAL_GROWTH_AUDIT.clear()
    prev._configure_modules()
    _base()._select_paper_trades = _select_dual_growth_supported_paper_trades


def _round(value: Any, digits: int = 6) -> float | None:
    return _base()._round(value, digits)


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dual_growth_context(row: dict[str, Any]) -> dict[str, Any]:
    revenue_pass = bool(row.get("revenue_growth_pass"))
    eps_pass = bool(row.get("eps_growth_pass"))
    passed = revenue_pass and eps_pass
    status = "dual_growth_pass" if passed else "missing_or_single_growth_pass"
    return {
        "dual_growth_status": status,
        "dual_growth_known_at": "SEC Companyfacts revenue/EPS filed date <= signal_date",
        "dual_growth_pass_v1": passed,
        "dual_growth_revenue_growth_pass": revenue_pass,
        "dual_growth_eps_growth_pass": eps_pass,
        "dual_growth_revenue_growth_status": row.get("revenue_growth_status"),
        "dual_growth_eps_growth_status": row.get("eps_growth_status"),
        "dual_growth_eps_growth_source": row.get("eps_growth_source"),
        "dual_growth_revenue_yoy_growth": _round(row.get("revenue_yoy_growth"), 6),
        "dual_growth_eps_yoy_growth": _round(row.get("eps_yoy_growth"), 6),
        "dual_growth_revenue_current_filed": row.get("revenue_current_filed"),
        "dual_growth_revenue_prior_filed": row.get("revenue_prior_filed"),
        "dual_growth_eps_current_filed": row.get("eps_current_filed"),
        "dual_growth_eps_prior_filed": row.get("eps_prior_filed"),
    }


def _dual_growth_scalar(context: dict[str, Any]) -> float:
    if context.get("dual_growth_pass_v1"):
        return DUAL_GROWTH_NOTIONAL_SCALAR
    return 1.0


def _select_dual_growth_supported_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = _base()
    governor = _governor()
    label = governor._window_label_for_candidates(candidates)
    balance_sheet_index = prev._balance_sheet_index_for_candidates(candidates)
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    pending_closes: list[dict[str, Any]] = []
    ticker_closed_pnl: defaultdict[str, float] = defaultdict(float)
    cumulative_closed_pnl = 0.0
    peak_closed_pnl = 0.0
    max_closed_drawdown_seen = 0.0
    audit: Counter[str] = Counter()
    supported_ticker_counts: Counter[str] = Counter()
    support_pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)
    status_counts: Counter[str] = Counter()

    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        if row.get("same_ticker_ab_overlap"):
            audit["same_ticker_core_overlap_filtered"] += 1
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= base.MAX_PAPER_TRADES_PER_DAY:
            audit["daily_top1_filtered"] += 1
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue

        trade = base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            audit["missing_trade_filtered"] += 1
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue

        entry_date = str(trade.get("entry_date") or signal_date)
        pending_closes, cumulative_closed_pnl, peak_closed_pnl, latest_dd = (
            governor._update_closed_state(
                pending_closes,
                entry_date,
                cumulative_closed_pnl,
                peak_closed_pnl,
                ticker_closed_pnl,
            )
        )
        max_closed_drawdown_seen = max(max_closed_drawdown_seen, latest_dd)
        closed_drawdown = peak_closed_pnl - cumulative_closed_pnl

        ticker_profit_scalar = (
            governor.TICKER_PROFIT_CAP_SCALAR
            if ticker_closed_pnl[ticker] >= governor.TICKER_CLOSED_PROFIT_CAP_USD
            else 1.0
        )
        global_drawdown_scalar = (
            governor.GLOBAL_DRAWDOWN_SCALAR
            if closed_drawdown >= governor.GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD
            else 1.0
        )
        low_volume_scalar = prev.prev.prev._low_volume_scalar(row)
        filing_recency_scalar = prev.prev._filing_recency_scalar(row)
        balance_context = balance_sheet_index.current_context(ticker, signal_date)
        balance_sheet_scalar = prev._balance_sheet_scalar(balance_context)
        dual_growth_context = _dual_growth_context(row)
        dual_growth_scalar = _dual_growth_scalar(dual_growth_context)
        notional_scalar_before_dual_growth = (
            ticker_profit_scalar
            * global_drawdown_scalar
            * low_volume_scalar
            * filing_recency_scalar
            * balance_sheet_scalar
        )
        notional_scalar = notional_scalar_before_dual_growth * dual_growth_scalar

        filing_age = prev.prev._operating_income_filing_age_days(row)
        balance_bucket = prev._liability_assets_bucket(balance_context.get("liabilities_assets_ratio"))
        status_counts[str(dual_growth_context.get("dual_growth_status") or "unknown")] += 1

        if ticker_profit_scalar < 1.0:
            audit["ticker_profit_cap_scaled"] += 1
        if global_drawdown_scalar < 1.0:
            audit["global_drawdown_scaled"] += 1
        if low_volume_scalar > 1.0:
            audit["low_volume_supported"] += 1
        if filing_recency_scalar > 1.0:
            audit["filing_recency_supported"] += 1
        if balance_sheet_scalar > 1.0:
            audit["low_liability_supported"] += 1
        if dual_growth_scalar > 1.0:
            audit["dual_growth_supported"] += 1
            supported_ticker_counts[ticker] += 1
        if ticker_profit_scalar < 1.0 and global_drawdown_scalar < 1.0:
            audit["both_governor_scalars_applied"] += 1

        base_notional = float(trade.get("paper_notional_usd") or base.BASE_NOTIONAL_USD)
        pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
        pre_dual_growth_notional = base_notional * notional_scalar_before_dual_growth
        supported_notional = base_notional * notional_scalar
        pre_dual_growth_pnl = pre_dual_growth_notional * pnl_pct_net
        supported_pnl = supported_notional * pnl_pct_net
        if dual_growth_scalar > 1.0:
            support_pnl_delta_by_ticker[ticker] += supported_pnl - pre_dual_growth_pnl

        supported_trade = {
            **trade,
            "closed_ledger_governor_rule_version": governor.RULE_VERSION,
            "closed_ledger_governor_trade_enabled": False,
            "closed_ledger_governor_alters_orders": False,
            "closed_ledger_governor_known_at": "closed paper ledger rows with exit_date < entry_date",
            "ticker_closed_profit_cap_usd": governor.TICKER_CLOSED_PROFIT_CAP_USD,
            "ticker_profit_cap_scalar": ticker_profit_scalar,
            "global_closed_drawdown_trigger_usd": governor.GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD,
            "global_drawdown_scalar": global_drawdown_scalar,
            "low_volume_participation_rule_version": prev.prev.prev.RULE_VERSION,
            "low_volume_participation_known_at": "daily OHLCV volume ratio with date <= signal_date",
            "low_volume_participation_trade_enabled": False,
            "low_volume_participation_alters_orders": False,
            "low_volume_ratio_20_max": prev.prev.prev.LOW_VOLUME_RATIO_MAX,
            "low_volume_ratio_20": _round(row.get("volume_ratio_20"), 6),
            "low_volume_participation_pass_v1": low_volume_scalar > 1.0,
            "low_volume_notional_scalar": low_volume_scalar,
            "filing_recency_rule_version": prev.prev.RULE_VERSION,
            "filing_recency_known_at": "SEC Companyfacts operating_income filed date <= signal_date",
            "filing_recency_trade_enabled": False,
            "filing_recency_alters_orders": False,
            "operating_income_current_filed": row.get("operating_income_current_filed"),
            "operating_income_filing_age_days": filing_age,
            "operating_income_filing_age_bucket": prev.prev._filing_age_bucket(filing_age),
            "filing_recency_max_days": prev.prev.FILING_RECENCY_MAX_DAYS,
            "filing_recency_pass_v1": filing_recency_scalar > 1.0,
            "filing_recency_notional_scalar": filing_recency_scalar,
            "low_liability_rule_version": prev.RULE_VERSION,
            "low_liability_known_at": "SEC Companyfacts assets/liabilities filed date <= signal_date",
            "low_liability_trade_enabled": False,
            "low_liability_alters_orders": False,
            "low_liability_assets_max": prev.LOW_LIABILITY_ASSETS_MAX,
            "low_liability_pass_v1": balance_sheet_scalar > 1.0,
            "low_liability_notional_scalar": balance_sheet_scalar,
            "liabilities_assets_bucket": balance_bucket,
            **balance_context,
            "dual_growth_rule_version": RULE_VERSION,
            "dual_growth_trade_enabled": False,
            "dual_growth_alters_orders": False,
            "dual_growth_notional_scalar": dual_growth_scalar,
            **dual_growth_context,
            "closed_ledger_notional_scalar": _round(notional_scalar, 6),
            "global_closed_pnl_before_entry": _round(cumulative_closed_pnl, 2),
            "global_closed_peak_pnl_before_entry": _round(peak_closed_pnl, 2),
            "global_closed_drawdown_before_entry": _round(closed_drawdown, 2),
            "ticker_closed_pnl_before_entry": _round(ticker_closed_pnl[ticker], 2),
            "paper_notional_usd": _round(supported_notional, 2),
            "pnl": _round(supported_pnl, 2),
            "pnl_without_dual_growth_support": _round(pre_dual_growth_pnl, 2),
            "dual_growth_support_pnl_delta": _round(supported_pnl - pre_dual_growth_pnl, 2),
            "selection_rule_version": RULE_VERSION,
            "rule_version": RULE_VERSION,
        }
        selected.append(supported_trade)
        used_date_counts[signal_date] += 1
        pending_closes.append(
            {
                "ticker": ticker,
                "exit_date": str(supported_trade.get("exit_date") or ""),
                "pnl": float(supported_trade.get("pnl") or 0.0),
            }
        )
        audit["selected_trades"] += 1

    for item in sorted(pending_closes, key=lambda row: str(row["exit_date"])):
        pnl = float(item.get("pnl") or 0.0)
        cumulative_closed_pnl += pnl
        peak_closed_pnl = max(peak_closed_pnl, cumulative_closed_pnl)
        max_closed_drawdown_seen = max(max_closed_drawdown_seen, peak_closed_pnl - cumulative_closed_pnl)

    DUAL_GROWTH_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "dual_growth_notional_scalar": DUAL_GROWTH_NOTIONAL_SCALAR,
        "input_candidates": len(candidates),
        "selected_trades": len(selected),
        "filtered_candidates": len(filtered),
        "dual_growth_supported": int(audit.get("dual_growth_supported", 0)),
        "low_liability_supported": int(audit.get("low_liability_supported", 0)),
        "filing_recency_supported": int(audit.get("filing_recency_supported", 0)),
        "low_volume_supported": int(audit.get("low_volume_supported", 0)),
        "final_closed_pnl": _round(cumulative_closed_pnl, 2),
        "max_closed_drawdown_seen_usd": _round(max_closed_drawdown_seen, 2),
        "selected_unique_tickers": len({str(row.get("ticker") or "").upper() for row in selected}),
        "selected_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in selected).items())
        ),
        "dual_growth_status_counts": dict(sorted(status_counts.items())),
        "dual_growth_supported_ticker_counts": dict(sorted(supported_ticker_counts.items())),
        "dual_growth_support_pnl_delta_by_ticker": {
            ticker: _round(delta, 2)
            for ticker, delta in sorted(support_pnl_delta_by_ticker.items())
        },
        **dict(sorted(audit.items())),
    }
    return selected, filtered


def _aggregate_metrics(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return prev._aggregate_metrics(metrics_by_window)


def _reference_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    ref_path = REPO_ROOT / "experiments" / "logs" / "exp-20260528-017.json"
    if not ref_path.exists():
        return {"available": False, "reason": "missing_exp_20260528_017_reference"}
    reference = json.loads(ref_path.read_text(encoding="utf-8"))
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
        "reference_experiment_id": "exp-20260528-017",
        "reference_decision": reference.get("decision"),
        "by_window_delta_after_vs_accepted_low_liability": by_window,
        "aggregate_delta_after_vs_accepted_low_liability": {
            "expected_value_score_delta_sum": _round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": _round(cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"], 2),
            "max_drawdown_pct_delta_max": _round(
                cur_agg["max_drawdown_pct_max"] - ref_agg["max_drawdown_pct_max"],
                6,
            ),
        },
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    reference_comparison = _reference_comparison(payload)
    current_stack_comparison_passed = False
    current_stack_failed_checks: list[str] = []
    if reference_comparison.get("available"):
        aggregate_ref = reference_comparison["aggregate_delta_after_vs_accepted_low_liability"]
        by_window_ref = reference_comparison["by_window_delta_after_vs_accepted_low_liability"]
        ref_ev_delta = float(aggregate_ref.get("expected_value_score_delta_sum") or 0.0)
        ref_pnl_delta = float(aggregate_ref.get("total_pnl_delta_sum") or 0.0)
        ref_ev_regressed = [
            label
            for label, row in by_window_ref.items()
            if float(row.get("expected_value_score_delta") or 0.0) < 0.0
        ]
        ref_pnl_regressed = [
            label
            for label, row in by_window_ref.items()
            if float(row.get("total_pnl_delta") or 0.0) < 0.0
        ]
        current_stack_comparison_passed = (
            ref_ev_delta > 0.0
            and ref_pnl_delta > 0.0
            and not ref_ev_regressed
            and not ref_pnl_regressed
        )
        if ref_ev_delta <= 0.0:
            current_stack_failed_checks.append("aggregate_ev_not_above_current_accepted_exp017")
        if ref_pnl_delta <= 0.0:
            current_stack_failed_checks.append("aggregate_pnl_not_above_current_accepted_exp017")
        if ref_ev_regressed:
            current_stack_failed_checks.append("window_ev_regressed_vs_current_accepted_exp017")
        if ref_pnl_regressed:
            current_stack_failed_checks.append("window_pnl_regressed_vs_current_accepted_exp017")
    else:
        current_stack_failed_checks.append("missing_current_accepted_exp017_reference")

    gate4_core_passed = bool(payload["gate4"]["passed"])
    gate4_passed = gate4_core_passed and current_stack_comparison_passed
    payload["gate4"]["core_gate4_passed"] = gate4_core_passed
    payload["gate4"]["current_accepted_stack_comparison_passed"] = current_stack_comparison_passed
    payload["gate4"]["current_accepted_stack_failed_checks"] = current_stack_failed_checks
    payload["gate4"]["passed"] = gate4_passed
    decision = (
        "accepted_candidate_fundamental_growth_rs_dual_growth_support"
        if gate4_passed
        else "rejected_fundamental_growth_rs_dual_growth_support"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / capital allocation: within the accepted Companyfacts "
        "operating-profit + RS paper source, candidates with both revenue and EPS "
        "growth passing may deserve a small default-off paper notional support. "
        "The prior dual-growth filter concentrated risk; this tests the same free "
        "SEC field only as a mild support on the accepted governed stack."
    )
    payload["change_type"] = "fundamental_growth_rs_dual_growth_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 19
    payload["nearby_prior_experiments"] = [
        "exp-20260527-020",
        "exp-20260528-004",
        "exp-20260528-006",
        "exp-20260528-008",
        "exp-20260528-012",
        "exp-20260528-015",
        "exp-20260528-016",
        "exp-20260528-017",
        "exp-20260528-019",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_sec_companyfacts_dual_growth_support_field"
    payload["parameters"]["dual_growth_support"] = {
        "paper_notional_scalar": DUAL_GROWTH_NOTIONAL_SCALAR,
        "applies_to": (
            "already selected exp-20260528-017 governed default-off paper trades "
            "after daily top-1 selection"
        ),
        "uses_future_data": False,
        "production_visible_field": (
            "revenue_growth_pass and eps_growth_pass computed from SEC Companyfacts "
            "with filed <= signal_date"
        ),
    }
    payload["parameters"]["locked_variables"] = [
        "all exp-20260528-017 low-liability logic",
        "all exp-20260528-016 filing-recency logic",
        "all exp-20260528-015 low-volume participation logic",
        "all exp-20260528-008 closed-ledger governor logic",
        "all exp-20260528-004 operating-profit quality logic",
        "all exp-20260527-017 Companyfacts growth thresholds",
        "all exp-20260527-017 RS proxy thresholds",
        "daily top-1 paper selection",
        "same-ticker core overlap skip",
        "paper notional base",
        "10-trading-day paper hold",
        "core signal generation",
        "core ranking",
        "core position sizing",
        "core exits",
        "portfolio heat",
        "slot rules",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
    ]
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / capital allocation alpha: PIT revenue-growth and "
            "EPS-growth confirmation is a distinct free SEC quality field for the "
            "accepted Companyfacts+RS paper pool when used as support, not a filter."
        ),
        "2_history_check": {
            "exp-20260527-020": (
                "Dual-growth as a hard candidate filter improved all windows versus "
                "the old source but failed drawdown/concentration."
            ),
            "exp-20260528-017": "Accepted low-liability support on the current governed Companyfacts+RS baseline.",
            "exp-20260528-016": "Accepted filing-recency support.",
            "exp-20260528-015": "Accepted low-volume participation support.",
            "exp-20260528-012": "Gross-margin expansion failed versus the accepted governed baseline.",
            "exp-20260528-006": "Cash-conversion quality failed drawdown/concentration.",
            "exp-20260528-019": "Working-capital support was rejected because selected trades had zero receivables/inventory coverage.",
            "current_difference": (
                "This run does not add a hard filter or retune growth, RS, margin, cash-flow, volume, "
                "filing-age, liabilities/assets, top-N, hold, or governor thresholds; "
                "it tests a small dual-growth support scalar on the accepted governed stack."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; ticker "
            "concentration inside guardrails; and no aggregate or window regression "
            "versus the current accepted exp-20260528-017 baseline."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260528_020_fundamental_growth_rs_dual_growth_support.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "revenue_growth_pass and eps_growth_pass fields computed from filed-date-safe Companyfacts",
    ]
    payload["gate2"]["note"] = (
        "The only new field is dual-growth confirmation, using existing "
        "filed-date-safe revenue and EPS growth flags. Paper entry remains next-open and the closed-ledger "
        "governor uses only rows with exit_date < entry_date."
    )
    payload["gate3"]["candidate_pool_changed"] = False
    payload["gate3"]["note"] = (
        "No core filter, live entry rule, or paper candidate filter was added. "
        "The rule scales default-off paper notional after selected candidate "
        "selection, so core survival is unchanged."
    )
    payload["dual_growth_audit"] = DUAL_GROWTH_AUDIT
    payload["reference_accepted_low_liability_exp017_comparison"] = reference_comparison
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, Kova, state-surface, "
        "broad-market, VCP/VBB threshold retunes, Companyfacts growth/RS/top-N/hold, "
        "cash-conversion, gross-margin, low-volume threshold, filing-recency "
        "threshold, liabilities/assets threshold, and closed-ledger governor retunes. "
        "This run tests only a small dual-growth support scalar on the accepted "
        "Companyfacts+RS paper source."
    )
    payload["interpretation"] = (
        "The dual-growth support cleared Gate 4 on top of the "
        "accepted exp-20260528-017 baseline. It is a candidate for a shared "
        "default-off adapter update with parity tests; it is not live capital activation."
        if gate4_passed
        else (
            "The dual-growth support did not clear Gate 4. Do not promote it or "
            "retry nearby dual-growth filters/scalars on the frozen windows without "
            "forward rows or materially new evidence."
        )
    )
    payload["next_evidence_needed"] = (
        "If accepted, move the same scalar into the shared default-off "
        "fundamental_growth_rs paper adapter with production metadata and focused "
        "parity tests, then collect forward replacement-value rows before any live activation."
    )
    payload["production_impact"].update(
        {
            "shared_policy_changed": gate4_passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": gate4_passed,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "default_off_paper_only": True,
            "replay_only": False if gate4_passed else True,
            "trade_enabled": False,
            "parity_test_added": gate4_passed,
            "promotion_requirement": (
                "Accepted result is retained only in the shared default-off "
                "fundamental_growth_rs paper adapter. Live/default activation still "
                "requires closed forward replacement-value rows and a separate "
                "Gate 1-4 trade adapter."
                if gate4_passed
                else (
                    "A retained positive result would require the same dual-growth "
                    "field in quant/fundamental_growth_rs_paper_sleeve.py, daily report "
                    "exposure, forward replacement-value ledger, and parity tests before "
                    "live/default behavior changes."
                )
            ),
        }
    )
    payload["related_files"] = [
        _base()._repo_rel(Path(__file__)),
        _base()._repo_rel(OUT_JSON),
        _base()._repo_rel(LOG_JSON),
        _base()._repo_rel(TICKET_JSON),
        _base()._repo_rel(DOC_TICKET_JSON),
        _base()._repo_rel(ARTIFACT_MD),
        _base()._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260528-020 Fundamental Growth + RS Dual-Growth Support",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: apply a 1.05x paper-notional support scalar to "
            "already selected governed Companyfacts+RS paper candidates whose "
            "filed-date-safe revenue-growth and EPS-growth checks both pass."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Dual-growth supported |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _base().WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["dual_growth_audit"].get(label, {})
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {supported} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                supported=audit.get("dual_growth_supported"),
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
            "## Dual-Growth Audit",
            "",
            "```json",
            json.dumps(payload["dual_growth_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Current Accepted Baseline Comparison",
            "",
            "```json",
            json.dumps(
                payload["reference_accepted_low_liability_exp017_comparison"],
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "If accepted, this remains shared default-off paper only. Live/default "
                "orders, core universe, core ranking, sizing, exits, LLM/news, and "
                "trade-enabled behavior remain unchanged."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _persist(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Fundamental growth + RS dual-growth support",
        "status": payload["decision"],
        "lane": "alpha_search",
        "updated_at": payload["timestamp"],
        "artifacts": {
            "json": _base()._repo_rel(OUT_JSON),
            "log": _base()._repo_rel(LOG_JSON),
            "report": _base()._repo_rel(ARTIFACT_MD),
        },
    }
    _base()._write_json(OUT_JSON, payload)
    _base()._write_json(LOG_JSON, payload)
    _base()._write_json(TICKET_JSON, ticket)
    _base()._write_json(DOC_TICKET_JSON, ticket)
    _base()._write_text(ARTIFACT_MD, _build_report(payload))
    _base()._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _update_payload(_base()._build_payload())
    _persist(payload)
    print(
        json.dumps(
            _base()._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "dual_growth_audit": payload["dual_growth_audit"],
                    "artifact": _base()._repo_rel(ARTIFACT_MD),
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
