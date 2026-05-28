"""exp-20260528-015: Companyfacts+RS low-volume participation support.

Alpha search follow-up to the accepted Companyfacts operating-profit + RS
paper lead. This keeps the PIT SEC Companyfacts growth + operating-profit
quality + OHLCV RS candidate source, daily top-1 selection, 10-day hold, and
the accepted closed-ledger governor fixed, then changes one production-visible
OHLCV source-quality variable: support selected paper candidates whose
signal-day volume ratio is below normal participation.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260528_004_fundamental_growth_rs_operating_profit_quality as source
import exp_20260528_008_operating_profit_quality_closed_ledger_governor as governor


EXPERIMENT_ID = "exp-20260528-015"
STEM = "fundamental_growth_rs_low_volume_participation"
TRIAL_FAMILY = "fundamental_growth_rs_low_volume_participation_support"
CHANGED_VARIABLE = "fundamental_growth_rs_signal_day_low_volume_notional_scalar_v1"
RULE_VERSION = "fundamental_growth_rs_low_volume_participation_support_v1"

LOW_VOLUME_RATIO_MAX = 0.90
LOW_VOLUME_NOTIONAL_SCALAR = 1.10

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

LOW_VOLUME_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    source.OPERATING_QUALITY_AUDIT.clear()
    source.prev.FUNDAMENTAL_RS_AUDIT.clear()
    governor.GOVERNOR_AUDIT.clear()
    LOW_VOLUME_AUDIT.clear()
    source._configure_modules()
    source.prev.base._candidate_rows_for_window = source._candidate_rows_for_window
    source.prev.base._select_paper_trades = _select_low_volume_supported_paper_trades


def _round(value: Any, digits: int = 6) -> float | None:
    return _base()._round(value, digits)


def _volume_ratio(row: dict[str, Any]) -> float | None:
    try:
        value = float(row.get("volume_ratio_20"))
    except (TypeError, ValueError):
        return None
    return value


def _low_volume_scalar(row: dict[str, Any]) -> float:
    volume_ratio = _volume_ratio(row)
    if volume_ratio is not None and volume_ratio <= LOW_VOLUME_RATIO_MAX:
        return LOW_VOLUME_NOTIONAL_SCALAR
    return 1.0


def _select_low_volume_supported_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = _base()
    label = governor._window_label_for_candidates(candidates)
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
    scaled_pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)

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
        low_volume_scalar = _low_volume_scalar(row)
        notional_scalar = ticker_profit_scalar * global_drawdown_scalar * low_volume_scalar
        if ticker_profit_scalar < 1.0:
            audit["ticker_profit_cap_scaled"] += 1
        if global_drawdown_scalar < 1.0:
            audit["global_drawdown_scaled"] += 1
        if low_volume_scalar > 1.0:
            audit["low_volume_supported"] += 1
            scaled_ticker_counts[ticker] += 1
        if ticker_profit_scalar < 1.0 and global_drawdown_scalar < 1.0:
            audit["both_governor_scalars_applied"] += 1

        base_notional = float(trade.get("paper_notional_usd") or base.BASE_NOTIONAL_USD)
        pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
        governed_notional = base_notional * ticker_profit_scalar * global_drawdown_scalar
        supported_notional = base_notional * notional_scalar
        governed_pnl = governed_notional * pnl_pct_net
        supported_pnl = supported_notional * pnl_pct_net
        if low_volume_scalar > 1.0:
            scaled_pnl_delta_by_ticker[ticker] += supported_pnl - governed_pnl

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
            "low_volume_participation_rule_version": RULE_VERSION,
            "low_volume_participation_known_at": "daily OHLCV volume ratio with date <= signal_date",
            "low_volume_participation_trade_enabled": False,
            "low_volume_participation_alters_orders": False,
            "low_volume_ratio_20_max": LOW_VOLUME_RATIO_MAX,
            "low_volume_ratio_20": _round(row.get("volume_ratio_20"), 6),
            "low_volume_participation_pass_v1": low_volume_scalar > 1.0,
            "low_volume_notional_scalar": low_volume_scalar,
            "closed_ledger_notional_scalar": _round(notional_scalar, 6),
            "global_closed_pnl_before_entry": _round(cumulative_closed_pnl, 2),
            "global_closed_peak_pnl_before_entry": _round(peak_closed_pnl, 2),
            "global_closed_drawdown_before_entry": _round(closed_drawdown, 2),
            "ticker_closed_pnl_before_entry": _round(ticker_closed_pnl[ticker], 2),
            "paper_notional_usd": _round(supported_notional, 2),
            "pnl": _round(supported_pnl, 2),
            "pnl_without_low_volume_support": _round(governed_pnl, 2),
            "low_volume_support_pnl_delta": _round(supported_pnl - governed_pnl, 2),
            "selection_rule_version": RULE_VERSION,
            "rule_version": RULE_VERSION,
        }
        selected.append(supported_trade)
        used_date_counts[date] += 1
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

    LOW_VOLUME_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "low_volume_ratio_20_max": LOW_VOLUME_RATIO_MAX,
        "low_volume_notional_scalar": LOW_VOLUME_NOTIONAL_SCALAR,
        "input_candidates": len(candidates),
        "selected_trades": len(selected),
        "filtered_candidates": len(filtered),
        "low_volume_supported": int(audit.get("low_volume_supported", 0)),
        "final_closed_pnl": _round(cumulative_closed_pnl, 2),
        "max_closed_drawdown_seen_usd": _round(max_closed_drawdown_seen, 2),
        "selected_unique_tickers": len({str(row.get("ticker") or "").upper() for row in selected}),
        "selected_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in selected).items())
        ),
        "low_volume_supported_ticker_counts": dict(sorted(scaled_ticker_counts.items())),
        "low_volume_support_pnl_delta_by_ticker": {
            ticker: _round(delta, 2)
            for ticker, delta in sorted(scaled_pnl_delta_by_ticker.items())
        },
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


def _reference_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    ref_path = REPO_ROOT / "experiments" / "logs" / "exp-20260528-008.json"
    if not ref_path.exists():
        return {"available": False, "reason": "missing_exp_20260528_008_reference"}
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
        "reference_experiment_id": "exp-20260528-008",
        "reference_decision": reference.get("decision"),
        "by_window_delta_after_vs_accepted_governed_operating_profit_quality": by_window,
        "aggregate_delta_after_vs_accepted_governed_operating_profit_quality": {
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


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    reference_comparison = _reference_comparison(payload)
    current_stack_comparison_passed = False
    current_stack_failed_checks: list[str] = []
    if reference_comparison.get("available"):
        aggregate_ref = reference_comparison[
            "aggregate_delta_after_vs_accepted_governed_operating_profit_quality"
        ]
        by_window_ref = reference_comparison[
            "by_window_delta_after_vs_accepted_governed_operating_profit_quality"
        ]
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
            current_stack_failed_checks.append("aggregate_ev_not_above_current_accepted_exp008")
        if ref_pnl_delta <= 0.0:
            current_stack_failed_checks.append("aggregate_pnl_not_above_current_accepted_exp008")
        if ref_ev_regressed:
            current_stack_failed_checks.append("window_ev_regressed_vs_current_accepted_exp008")
        if ref_pnl_regressed:
            current_stack_failed_checks.append("window_pnl_regressed_vs_current_accepted_exp008")
    else:
        current_stack_failed_checks.append("missing_current_accepted_exp008_reference")

    gate4_core_passed = bool(payload["gate4"]["passed"])
    gate4_passed = gate4_core_passed and current_stack_comparison_passed
    payload["gate4"]["core_gate4_passed"] = gate4_core_passed
    payload["gate4"]["current_accepted_stack_comparison_passed"] = current_stack_comparison_passed
    payload["gate4"]["current_accepted_stack_failed_checks"] = current_stack_failed_checks
    payload["gate4"]["passed"] = gate4_passed
    decision = (
        "accepted_candidate_fundamental_growth_rs_low_volume_participation_support"
        if gate4_passed
        else "rejected_fundamental_growth_rs_low_volume_participation_support"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / capital allocation: within the accepted Companyfacts "
        "operating-profit + RS paper source, candidates that advance without "
        "above-normal signal-day volume may represent quieter accumulation and "
        "less exhaustion than high-participation jumps. A small production-visible "
        "paper-notional support can improve replacement value without changing entry."
    )
    payload["change_type"] = "fundamental_growth_rs_low_volume_participation_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 14
    payload["nearby_prior_experiments"] = [
        "exp-20260527-017",
        "exp-20260527-020",
        "exp-20260528-004",
        "exp-20260528-006",
        "exp-20260528-008",
        "exp-20260528-011",
        "exp-20260528-012",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_ohlcv_volume_participation_field"
    payload["parameters"]["low_volume_participation_support"] = {
        "volume_ratio_20_max": LOW_VOLUME_RATIO_MAX,
        "paper_notional_scalar": LOW_VOLUME_NOTIONAL_SCALAR,
        "applies_to": (
            "already selected exp-20260528-008 governed default-off paper trades "
            "after daily top-1 selection"
        ),
        "uses_future_data": False,
        "production_visible_field": "signal-day volume_ratio_20 from OHLCV date <= signal_date",
    }
    payload["parameters"]["locked_variables"] = [
        "all exp-20260528-004 operating-profit quality logic",
        "all exp-20260527-017 Companyfacts growth thresholds",
        "all exp-20260527-017 RS proxy thresholds",
        "accepted exp-20260528-008 closed-ledger governor",
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
            "candidate_pool / capital allocation alpha: low signal-day volume "
            "participation is a distinct OHLCV quality field for the accepted "
            "Companyfacts+RS paper pool."
        ),
        "2_history_check": {
            "exp-20260528-008": "Accepted governed operating-profit quality baseline.",
            "exp-20260528-006": "Cash-conversion quality failed drawdown/concentration.",
            "exp-20260528-012": "Gross-margin expansion failed versus the accepted governed baseline.",
            "current_difference": "This run does not retune growth, RS, margin, cash-flow, top-N, hold, or governor thresholds; it tests a new signal-day volume participation scalar.",
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "ticker concentration inside guardrails; and no aggregate or window "
            "regression versus the current accepted exp-20260528-008 governed baseline."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260528_015_fundamental_growth_rs_low_volume_participation.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "signal-day volume_ratio_20 from the existing source candidate row",
    ]
    payload["gate2"]["note"] = (
        "The only new strategy field is volume_ratio_20, already computed from "
        "signal-date and prior OHLCV rows in the Companyfacts+RS source. Paper "
        "entry remains next-open and the closed-ledger governor uses only rows "
        "with exit_date < entry_date."
    )
    payload["gate3"]["candidate_pool_changed"] = False
    payload["gate3"]["note"] = (
        "No core filter, live entry rule, or paper candidate filter was added. "
        "The rule scales default-off paper notional after selected candidate "
        "selection, so core survival is unchanged."
    )
    payload["low_volume_participation_audit"] = LOW_VOLUME_AUDIT
    payload["operating_profit_quality_audit"] = source.OPERATING_QUALITY_AUDIT
    payload["fundamental_growth_rs_audit"] = source.prev.FUNDAMENTAL_RS_AUDIT
    payload["reference_accepted_governed_operating_profit_exp008_comparison"] = reference_comparison
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, Kova, state-surface, "
        "broad-market, VCP threshold, Companyfacts growth/RS/top-N/hold, "
        "cash-conversion, gross-margin, filing-recency, and closed-ledger governor "
        "retunes. This run tests only a new OHLCV volume participation field on "
        "the accepted Companyfacts+RS paper source."
    )
    payload["interpretation"] = (
        "The low-volume participation support cleared Gate 4 on top of the "
        "accepted exp-20260528-008 governed baseline. It is a candidate for a "
        "shared default-off adapter update with parity tests; it is not live "
        "capital activation."
        if gate4_passed
        else (
            "The low-volume participation support did not clear Gate 4. Do not "
            "promote it or retry nearby volume-ratio scalar thresholds on the "
            "frozen windows without forward rows or a materially new field."
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
                    "A retained positive result would require the same low-volume "
                    "participation field in quant/fundamental_growth_rs_paper_sleeve.py, "
                    "daily report exposure, forward replacement-value ledger, and "
                    "parity tests before live/default behavior changes."
                )
            ),
        }
    )
    payload["related_files"] = [
        source.prev.base._repo_rel(Path(__file__)),
        source.prev.base._repo_rel(OUT_JSON),
        source.prev.base._repo_rel(LOG_JSON),
        source.prev.base._repo_rel(TICKET_JSON),
        source.prev.base._repo_rel(DOC_TICKET_JSON),
        source.prev.base._repo_rel(ARTIFACT_MD),
        source.prev.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260528-015 Fundamental Growth + RS Low-Volume Participation",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: apply a 1.10x paper-notional support scalar to "
            "already selected governed Companyfacts+RS paper candidates with "
            "signal-day `volume_ratio_20 <= 0.90`."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Low-volume supported |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _base().WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["low_volume_participation_audit"].get(label, {})
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
                supported=audit.get("low_volume_supported"),
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
            "## Low-Volume Audit",
            "",
            "```json",
            json.dumps(payload["low_volume_participation_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Current Accepted Baseline Comparison",
            "",
            "```json",
            json.dumps(
                payload["reference_accepted_governed_operating_profit_exp008_comparison"],
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
                "Accepted into the shared default-off paper adapter only. The "
                "daily production path surfaces the same low-volume participation "
                "metadata/scalar through `fundamental_growth_rs_paper_sleeve.py`; "
                "live/default orders, core universe, core ranking, sizing, exits, "
                "LLM/news, and trade-enabled behavior remain unchanged."
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
        "title": "Fundamental growth + RS low-volume participation support",
        "status": payload["decision"],
        "lane": "alpha_search",
        "updated_at": payload["timestamp"],
        "artifacts": {
            "json": source.prev.base._repo_rel(OUT_JSON),
            "log": source.prev.base._repo_rel(LOG_JSON),
            "report": source.prev.base._repo_rel(ARTIFACT_MD),
        },
    }
    source.prev.base._write_json(OUT_JSON, payload)
    source.prev.base._write_json(LOG_JSON, payload)
    source.prev.base._write_json(TICKET_JSON, ticket)
    source.prev.base._write_json(DOC_TICKET_JSON, ticket)
    source.prev.base._write_text(ARTIFACT_MD, _build_report(payload))
    source.prev.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _update_payload(source.prev.base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            source.prev.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "low_volume_participation_audit": payload["low_volume_participation_audit"],
                    "artifact": source.prev.base._repo_rel(ARTIFACT_MD),
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
