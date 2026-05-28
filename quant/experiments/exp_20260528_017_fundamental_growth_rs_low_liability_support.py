"""exp-20260528-017: Companyfacts+RS low-liability balance-sheet support.

Alpha search follow-up to the accepted Companyfacts operating-profit + RS
paper lead, low-volume participation support, and filing-recency support.
This keeps the candidate source, daily top-1 selection, 10-day hold,
closed-ledger governor, low-volume support, and filing-recency support fixed.
It changes one production-visible free SEC field: support selected paper
candidates whose latest PIT liabilities/assets ratio is low.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260528_016_fundamental_growth_rs_filing_recency_support as prev


EXPERIMENT_ID = "exp-20260528-017"
STEM = "fundamental_growth_rs_low_liability_support"
TRIAL_FAMILY = "fundamental_growth_rs_low_liability_balance_sheet_support"
CHANGED_VARIABLE = "fundamental_growth_rs_low_liability_assets_notional_scalar_v1"
RULE_VERSION = "fundamental_growth_rs_low_liability_support_v1"

LOW_LIABILITY_ASSETS_MAX = 0.35
LOW_LIABILITY_NOTIONAL_SCALAR = 1.05

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BALANCE_SHEET_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _base():
    return prev._base()


def _source_base():
    return prev.prev.source.prev


def _governor():
    return prev.prev.governor


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
    prev.FILING_RECENCY_AUDIT.clear()
    BALANCE_SHEET_AUDIT.clear()
    prev._configure_modules()
    _base()._select_paper_trades = _select_low_liability_supported_paper_trades


def _round(value: Any, digits: int = 6) -> float | None:
    return _base()._round(value, digits)


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _balance_sheet_sort_key(row: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(row.get("end") or ""),
        str(row.get("filed") or "")[:10],
        1 if str(row.get("form") or "").upper() == "10-Q" else 0,
    )


class CompanyfactsBalanceSheetIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = _date10(raw.get("filed") or raw.get("asof_date"))
            value = _float(raw.get("value") if "value" in raw else raw.get("current_value"))
            if canonical not in {"assets", "liabilities"}:
                continue
            if not ticker or not filed or value is None:
                continue
            by_key[(ticker, canonical)].append(
                {
                    **raw,
                    "ticker": ticker,
                    "canonical": canonical,
                    "filed": filed,
                    "value": value,
                    "end": raw.get("end") if raw.get("end") else raw.get("current_period_end"),
                    "form": raw.get("form") if raw.get("form") else raw.get("current_form"),
                }
            )
        for bucket in by_key.values():
            bucket.sort(key=_balance_sheet_sort_key)
        self.by_key = by_key

    def current_context(self, ticker: str, asof_date: str) -> dict[str, Any]:
        ticker = ticker.upper()
        assets_rows = [
            row
            for row in self.by_key.get((ticker, "assets"), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        liabilities_rows = [
            row
            for row in self.by_key.get((ticker, "liabilities"), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not assets_rows:
            return {
                "balance_sheet_status": "missing_assets",
                "balance_sheet_known_at": "SEC Companyfacts filed date <= signal_date",
                "liabilities_assets_ratio": None,
            }
        if not liabilities_rows:
            return {
                "balance_sheet_status": "missing_liabilities",
                "balance_sheet_known_at": "SEC Companyfacts filed date <= signal_date",
                "assets_current_value": _round(assets_rows[-1].get("value"), 6),
                "assets_current_filed": assets_rows[-1].get("filed"),
                "assets_current_period_end": assets_rows[-1].get("end"),
                "liabilities_assets_ratio": None,
            }
        assets = assets_rows[-1]
        same_end_liabilities = [
            row for row in liabilities_rows if row.get("end") == assets.get("end")
        ]
        liabilities = same_end_liabilities[-1] if same_end_liabilities else liabilities_rows[-1]
        assets_value = _float(assets.get("value"))
        liabilities_value = _float(liabilities.get("value"))
        if assets_value is None or assets_value <= 0.0 or liabilities_value is None:
            ratio = None
            status = "invalid_balance_sheet_value"
        else:
            ratio = liabilities_value / assets_value
            status = "ok"
        return {
            "balance_sheet_status": status,
            "balance_sheet_known_at": "SEC Companyfacts filed date <= signal_date",
            "assets_current_value": _round(assets_value, 6),
            "assets_current_filed": assets.get("filed"),
            "assets_current_period_end": assets.get("end"),
            "liabilities_current_value": _round(liabilities_value, 6),
            "liabilities_current_filed": liabilities.get("filed"),
            "liabilities_current_period_end": liabilities.get("end"),
            "liabilities_assets_ratio": _round(ratio, 6),
        }


def _balance_sheet_index_for_candidates(
    candidates: list[dict[str, Any]],
) -> CompanyfactsBalanceSheetIndex:
    tickers = sorted({str(row.get("ticker") or "").upper() for row in candidates})
    max_filed = max((_date10(row.get("date") or row.get("signal_date")) for row in candidates), default="")
    rows = _source_base()._load_companyfacts_rows(max_filed=max_filed, tickers=tickers)
    return CompanyfactsBalanceSheetIndex(rows)


def _liability_assets_bucket(value: Any) -> str:
    ratio = _float(value)
    if ratio is None:
        return "missing"
    if ratio <= LOW_LIABILITY_ASSETS_MAX:
        return "low_lte_0p35"
    if ratio < 0.55:
        return "medium_0p35_0p55"
    if ratio < 0.75:
        return "higher_0p55_0p75"
    return "high_gte_0p75"


def _balance_sheet_scalar(context: dict[str, Any]) -> float:
    ratio = _float(context.get("liabilities_assets_ratio"))
    if ratio is not None and ratio <= LOW_LIABILITY_ASSETS_MAX:
        return LOW_LIABILITY_NOTIONAL_SCALAR
    return 1.0


def _select_low_liability_supported_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = _base()
    governor = _governor()
    label = governor._window_label_for_candidates(candidates)
    balance_sheet_index = _balance_sheet_index_for_candidates(candidates)
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
    balance_bucket_counts: Counter[str] = Counter()
    balance_status_counts: Counter[str] = Counter()
    supported_pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)

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
        low_volume_scalar = prev.prev._low_volume_scalar(row)
        filing_recency_scalar = prev._filing_recency_scalar(row)
        balance_context = balance_sheet_index.current_context(ticker, signal_date)
        balance_sheet_scalar = _balance_sheet_scalar(balance_context)
        notional_scalar = (
            ticker_profit_scalar
            * global_drawdown_scalar
            * low_volume_scalar
            * filing_recency_scalar
            * balance_sheet_scalar
        )
        filing_age = prev._operating_income_filing_age_days(row)
        balance_bucket = _liability_assets_bucket(balance_context.get("liabilities_assets_ratio"))
        balance_bucket_counts[balance_bucket] += 1
        balance_status_counts[str(balance_context.get("balance_sheet_status") or "unknown")] += 1

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
            supported_ticker_counts[ticker] += 1
        if ticker_profit_scalar < 1.0 and global_drawdown_scalar < 1.0:
            audit["both_governor_scalars_applied"] += 1

        base_notional = float(trade.get("paper_notional_usd") or base.BASE_NOTIONAL_USD)
        pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
        pre_balance_notional = (
            base_notional
            * ticker_profit_scalar
            * global_drawdown_scalar
            * low_volume_scalar
            * filing_recency_scalar
        )
        supported_notional = base_notional * notional_scalar
        pre_balance_pnl = pre_balance_notional * pnl_pct_net
        supported_pnl = supported_notional * pnl_pct_net
        if balance_sheet_scalar > 1.0:
            supported_pnl_delta_by_ticker[ticker] += supported_pnl - pre_balance_pnl

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
            "low_volume_participation_rule_version": prev.prev.RULE_VERSION,
            "low_volume_participation_known_at": "daily OHLCV volume ratio with date <= signal_date",
            "low_volume_participation_trade_enabled": False,
            "low_volume_participation_alters_orders": False,
            "low_volume_ratio_20_max": prev.prev.LOW_VOLUME_RATIO_MAX,
            "low_volume_ratio_20": _round(row.get("volume_ratio_20"), 6),
            "low_volume_participation_pass_v1": low_volume_scalar > 1.0,
            "low_volume_notional_scalar": low_volume_scalar,
            "filing_recency_rule_version": prev.RULE_VERSION,
            "filing_recency_known_at": "SEC Companyfacts operating_income filed date <= signal_date",
            "filing_recency_trade_enabled": False,
            "filing_recency_alters_orders": False,
            "operating_income_current_filed": row.get("operating_income_current_filed"),
            "operating_income_filing_age_days": filing_age,
            "operating_income_filing_age_bucket": prev._filing_age_bucket(filing_age),
            "filing_recency_max_days": prev.FILING_RECENCY_MAX_DAYS,
            "filing_recency_pass_v1": filing_recency_scalar > 1.0,
            "filing_recency_notional_scalar": filing_recency_scalar,
            "low_liability_rule_version": RULE_VERSION,
            "low_liability_known_at": "SEC Companyfacts assets/liabilities filed date <= signal_date",
            "low_liability_trade_enabled": False,
            "low_liability_alters_orders": False,
            "low_liability_assets_max": LOW_LIABILITY_ASSETS_MAX,
            "low_liability_pass_v1": balance_sheet_scalar > 1.0,
            "low_liability_notional_scalar": balance_sheet_scalar,
            "liabilities_assets_bucket": balance_bucket,
            **balance_context,
            "closed_ledger_notional_scalar": _round(notional_scalar, 6),
            "global_closed_pnl_before_entry": _round(cumulative_closed_pnl, 2),
            "global_closed_peak_pnl_before_entry": _round(peak_closed_pnl, 2),
            "global_closed_drawdown_before_entry": _round(closed_drawdown, 2),
            "ticker_closed_pnl_before_entry": _round(ticker_closed_pnl[ticker], 2),
            "paper_notional_usd": _round(supported_notional, 2),
            "pnl": _round(supported_pnl, 2),
            "pnl_without_low_liability_support": _round(pre_balance_pnl, 2),
            "low_liability_support_pnl_delta": _round(supported_pnl - pre_balance_pnl, 2),
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

    BALANCE_SHEET_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "low_liability_assets_max": LOW_LIABILITY_ASSETS_MAX,
        "low_liability_notional_scalar": LOW_LIABILITY_NOTIONAL_SCALAR,
        "input_candidates": len(candidates),
        "selected_trades": len(selected),
        "filtered_candidates": len(filtered),
        "low_liability_supported": int(audit.get("low_liability_supported", 0)),
        "low_volume_supported": int(audit.get("low_volume_supported", 0)),
        "filing_recency_supported": int(audit.get("filing_recency_supported", 0)),
        "final_closed_pnl": _round(cumulative_closed_pnl, 2),
        "max_closed_drawdown_seen_usd": _round(max_closed_drawdown_seen, 2),
        "selected_unique_tickers": len({str(row.get("ticker") or "").upper() for row in selected}),
        "selected_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in selected).items())
        ),
        "liabilities_assets_bucket_counts": dict(sorted(balance_bucket_counts.items())),
        "balance_sheet_status_counts": dict(sorted(balance_status_counts.items())),
        "low_liability_supported_ticker_counts": dict(sorted(supported_ticker_counts.items())),
        "low_liability_support_pnl_delta_by_ticker": {
            ticker: _round(delta, 2)
            for ticker, delta in sorted(supported_pnl_delta_by_ticker.items())
        },
        **dict(sorted(audit.items())),
    }
    return selected, filtered


def _aggregate_metrics(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return prev._aggregate_metrics(metrics_by_window)


def _reference_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    ref_path = REPO_ROOT / "experiments" / "logs" / "exp-20260528-016.json"
    if not ref_path.exists():
        return {"available": False, "reason": "missing_exp_20260528_016_reference"}
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
        "reference_experiment_id": "exp-20260528-016",
        "reference_decision": reference.get("decision"),
        "by_window_delta_after_vs_accepted_filing_recency": by_window,
        "aggregate_delta_after_vs_accepted_filing_recency": {
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
        aggregate_ref = reference_comparison["aggregate_delta_after_vs_accepted_filing_recency"]
        by_window_ref = reference_comparison["by_window_delta_after_vs_accepted_filing_recency"]
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
            current_stack_failed_checks.append("aggregate_ev_not_above_current_accepted_exp016")
        if ref_pnl_delta <= 0.0:
            current_stack_failed_checks.append("aggregate_pnl_not_above_current_accepted_exp016")
        if ref_ev_regressed:
            current_stack_failed_checks.append("window_ev_regressed_vs_current_accepted_exp016")
        if ref_pnl_regressed:
            current_stack_failed_checks.append("window_pnl_regressed_vs_current_accepted_exp016")
    else:
        current_stack_failed_checks.append("missing_current_accepted_exp016_reference")

    gate4_core_passed = bool(payload["gate4"]["passed"])
    gate4_passed = gate4_core_passed and current_stack_comparison_passed
    payload["gate4"]["core_gate4_passed"] = gate4_core_passed
    payload["gate4"]["current_accepted_stack_comparison_passed"] = current_stack_comparison_passed
    payload["gate4"]["current_accepted_stack_failed_checks"] = current_stack_failed_checks
    payload["gate4"]["passed"] = gate4_passed
    decision = (
        "accepted_candidate_fundamental_growth_rs_low_liability_support"
        if gate4_passed
        else "rejected_fundamental_growth_rs_low_liability_support"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / capital allocation: within the accepted Companyfacts "
        "operating-profit + RS paper source, low liabilities/assets is a distinct "
        "balance-sheet quality field. A small default-off paper notional support "
        "should improve replacement value and reduce APP concentration by adding "
        "weight to low-leverage winners such as MU, PLTR, CRDO, and GOOG."
    )
    payload["change_type"] = "fundamental_growth_rs_low_liability_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 17
    payload["nearby_prior_experiments"] = [
        "exp-20260528-004",
        "exp-20260528-006",
        "exp-20260528-008",
        "exp-20260528-012",
        "exp-20260528-015",
        "exp-20260528-016",
        "exp-20260527-903",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_sec_companyfacts_balance_sheet_quality_field"
    payload["parameters"]["low_liability_support"] = {
        "liabilities_assets_max": LOW_LIABILITY_ASSETS_MAX,
        "paper_notional_scalar": LOW_LIABILITY_NOTIONAL_SCALAR,
        "applies_to": (
            "already selected exp-20260528-016 governed default-off paper trades "
            "after daily top-1 selection"
        ),
        "uses_future_data": False,
        "production_visible_field": (
            "latest assets and liabilities from SEC Companyfacts with filed <= signal_date; "
            "liabilities prefer the same period_end as the latest assets row"
        ),
    }
    payload["parameters"]["locked_variables"] = [
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
            "candidate_pool / capital allocation alpha: low PIT liabilities/assets "
            "is a free SEC balance-sheet quality field for the accepted Companyfacts+RS paper pool."
        ),
        "2_history_check": {
            "exp-20260528-016": "Accepted filing-recency support but max positive share was near the 0.40 guardrail.",
            "exp-20260528-015": "Accepted low-volume participation support.",
            "exp-20260528-012": "Gross-margin expansion failed versus the accepted governed baseline.",
            "share_count_diagnostic": (
                "Share-count non-dilution support was skipped because it primarily "
                "boosted APP and would worsen concentration."
            ),
            "current_difference": (
                "This run does not retune growth, RS, margin, cash-flow, volume, "
                "filing-age, top-N, hold, sector cap, or governor thresholds; it "
                "tests a balance-sheet leverage field."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; ticker "
            "concentration inside guardrails; and no aggregate or window regression "
            "versus the current accepted exp-20260528-016 baseline."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260528_017_fundamental_growth_rs_low_liability_support.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "assets and liabilities facts filed <= signal_date",
    ]
    payload["gate2"]["note"] = (
        "The only new strategy field is liabilities/assets, computed from "
        "Companyfacts assets/liabilities filed dates that are <= signal_date. "
        "Paper entry remains next-open and the closed-ledger governor uses only "
        "rows with exit_date < entry_date."
    )
    payload["gate3"]["candidate_pool_changed"] = False
    payload["gate3"]["note"] = (
        "No core filter, live entry rule, or paper candidate filter was added. "
        "The rule scales default-off paper notional after selected candidate "
        "selection, so core survival is unchanged."
    )
    payload["balance_sheet_audit"] = BALANCE_SHEET_AUDIT
    payload["filing_recency_audit"] = prev.FILING_RECENCY_AUDIT
    payload["low_volume_participation_audit"] = prev.prev.LOW_VOLUME_AUDIT
    payload["operating_profit_quality_audit"] = prev.prev.source.OPERATING_QUALITY_AUDIT
    payload["fundamental_growth_rs_audit"] = prev.prev.source.prev.FUNDAMENTAL_RS_AUDIT
    payload["reference_accepted_filing_recency_exp016_comparison"] = reference_comparison
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, Kova, state-surface, "
        "broad-market, VCP threshold, Companyfacts growth/RS/top-N/hold, "
        "cash-conversion, gross-margin, filing-recency threshold, low-volume "
        "threshold, share-count non-dilution support, and closed-ledger governor "
        "retunes. This run tests only a new SEC balance-sheet field on the "
        "accepted Companyfacts+RS paper source."
    )
    payload["interpretation"] = (
        "The low-liability balance-sheet support cleared Gate 4 on top of the "
        "accepted exp-20260528-016 baseline. It is a candidate for a shared "
        "default-off adapter update with parity tests; it is not live capital activation."
        if gate4_passed
        else (
            "The low-liability balance-sheet support did not clear Gate 4. Do not "
            "promote it or retry nearby liabilities/assets thresholds/scalars on "
            "the frozen windows without forward rows or a materially new balance-sheet field."
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
                    "A retained positive result would require the same liabilities/assets "
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
        "# exp-20260528-017 Fundamental Growth + RS Low-Liability Support",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: apply a 1.05x paper-notional support scalar to "
            "already selected governed Companyfacts+RS paper candidates whose "
            "latest PIT liabilities/assets ratio is <= 0.35."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Low-liability supported |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _base().WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["balance_sheet_audit"].get(label, {})
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
                supported=audit.get("low_liability_supported"),
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
            "## Balance-Sheet Audit",
            "",
            "```json",
            json.dumps(payload["balance_sheet_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Current Accepted Baseline Comparison",
            "",
            "```json",
            json.dumps(
                payload["reference_accepted_filing_recency_exp016_comparison"],
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
        "title": "Fundamental growth + RS low-liability support",
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
                    "balance_sheet_audit": payload["balance_sheet_audit"],
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
