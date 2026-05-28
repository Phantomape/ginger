"""exp-20260528-019: Companyfacts+RS working-capital discipline support.

Alpha search follow-up to the accepted Companyfacts operating-profit + RS
paper lead, low-volume support, filing-recency support, and low-liability
support. This keeps the accepted candidate source, daily top-1 selection,
10-day hold, closed-ledger governor, and all prior paper-notional supports
fixed. It changes one production-visible free SEC field: support selected
paper candidates whose PIT working-capital ratios are not deteriorating
materially versus the prior-year same quarter.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260528_017_fundamental_growth_rs_low_liability_support as prev


EXPERIMENT_ID = "exp-20260528-019"
STEM = "fundamental_growth_rs_working_capital_discipline"
TRIAL_FAMILY = "fundamental_growth_rs_working_capital_discipline_support"
CHANGED_VARIABLE = "fundamental_growth_rs_working_capital_discipline_notional_scalar_v1"
RULE_VERSION = "fundamental_growth_rs_working_capital_discipline_support_v1"

MAX_WORKING_CAPITAL_RATIO_DETERIORATION = 0.05
WORKING_CAPITAL_NOTIONAL_SCALAR = 1.05

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WORKING_CAPITAL_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    WORKING_CAPITAL_AUDIT.clear()
    prev._configure_modules()
    _base()._select_paper_trades = _select_working_capital_supported_paper_trades


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


def _fact_sort_key(row: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(row.get("end") or ""),
        str(row.get("filed") or "")[:10],
        1 if str(row.get("form") or "").upper() == "10-Q" else 0,
    )


class CompanyfactsWorkingCapitalIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = _date10(raw.get("filed") or raw.get("asof_date"))
            value = _float(raw.get("value") if "value" in raw else raw.get("current_value"))
            if canonical not in {"revenue", "receivables", "inventory"}:
                continue
            if not ticker or not filed or value is None or not _source_base()._is_quarterly_fact(raw):
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
                    "fy_int": _int_or_none(raw.get("fy")),
                    "fp_norm": str(raw.get("fp") or raw.get("current_fp") or "").upper(),
                }
            )
        for bucket in by_key.values():
            bucket.sort(key=_fact_sort_key)
        self.by_key = by_key

    def latest_fact(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any] | None:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if _date10(row.get("filed")) <= asof_date
        ]
        return rows[-1] if rows else None

    def matching_fact(
        self,
        ticker: str,
        canonical: str,
        asof_date: str,
        *,
        end: str | None = None,
        fy: int | None = None,
        fp: str | None = None,
    ) -> dict[str, Any] | None:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if _date10(row.get("filed")) <= asof_date
        ]
        if end:
            rows = [row for row in rows if str(row.get("end") or "") == end]
        if fy is not None:
            rows = [row for row in rows if row.get("fy_int") == fy]
        if fp:
            rows = [row for row in rows if row.get("fp_norm") == fp]
        return rows[-1] if rows else None

    def current_context(self, ticker: str, asof_date: str) -> dict[str, Any]:
        ticker = ticker.upper()
        revenue = self.latest_fact(ticker, "revenue", asof_date)
        if revenue is None:
            return {
                "working_capital_status": "missing_current_revenue",
                "working_capital_known_at": "SEC Companyfacts filed date <= signal_date",
                "working_capital_discipline_pass_v1": False,
            }
        revenue_value = _float(revenue.get("value"))
        if revenue_value is None or revenue_value <= 0.0:
            return {
                "working_capital_status": "invalid_current_revenue",
                "working_capital_known_at": "SEC Companyfacts filed date <= signal_date",
                "working_capital_discipline_pass_v1": False,
                "working_capital_revenue_current_value": _round(revenue_value, 6),
                "working_capital_revenue_current_filed": revenue.get("filed"),
                "working_capital_revenue_current_period_end": revenue.get("end"),
            }

        fy = revenue.get("fy_int")
        fp = revenue.get("fp_norm")
        prior_revenue = None
        if fy is not None and fp:
            prior_revenue = self.matching_fact(
                ticker,
                "revenue",
                asof_date,
                fy=int(fy) - 1,
                fp=str(fp),
            )
        prior_revenue_value = _float(prior_revenue.get("value")) if prior_revenue else None
        if prior_revenue_value is None or prior_revenue_value <= 0.0:
            return {
                "working_capital_status": "missing_prior_revenue_same_quarter",
                "working_capital_known_at": "SEC Companyfacts filed date <= signal_date",
                "working_capital_discipline_pass_v1": False,
                "working_capital_revenue_current_value": _round(revenue_value, 6),
                "working_capital_revenue_current_filed": revenue.get("filed"),
                "working_capital_revenue_current_period_end": revenue.get("end"),
            }

        metrics: dict[str, Any] = {
            "working_capital_status": "ok",
            "working_capital_known_at": "SEC Companyfacts filed date <= signal_date",
            "working_capital_revenue_current_value": _round(revenue_value, 6),
            "working_capital_revenue_current_filed": revenue.get("filed"),
            "working_capital_revenue_current_period_end": revenue.get("end"),
            "working_capital_revenue_prior_value": _round(prior_revenue_value, 6),
            "working_capital_revenue_prior_filed": prior_revenue.get("filed") if prior_revenue else None,
            "working_capital_revenue_prior_period_end": prior_revenue.get("end") if prior_revenue else None,
            "max_working_capital_ratio_deterioration": MAX_WORKING_CAPITAL_RATIO_DETERIORATION,
        }
        available = 0
        pass_flags: list[bool] = []
        for canonical in ("receivables", "inventory"):
            current = self.matching_fact(ticker, canonical, asof_date, end=str(revenue.get("end") or ""))
            prior = None
            if prior_revenue is not None:
                prior = self.matching_fact(
                    ticker,
                    canonical,
                    asof_date,
                    end=str(prior_revenue.get("end") or ""),
                )
            cur_value = _float(current.get("value")) if current else None
            prior_value = _float(prior.get("value")) if prior else None
            cur_ratio = cur_value / revenue_value if cur_value is not None else None
            prior_ratio = prior_value / prior_revenue_value if prior_value is not None else None
            delta = cur_ratio - prior_ratio if cur_ratio is not None and prior_ratio is not None else None
            metrics[f"{canonical}_current_value"] = _round(cur_value, 6)
            metrics[f"{canonical}_current_filed"] = current.get("filed") if current else None
            metrics[f"{canonical}_current_period_end"] = current.get("end") if current else None
            metrics[f"{canonical}_prior_value"] = _round(prior_value, 6)
            metrics[f"{canonical}_prior_filed"] = prior.get("filed") if prior else None
            metrics[f"{canonical}_prior_period_end"] = prior.get("end") if prior else None
            metrics[f"{canonical}_revenue_ratio_current"] = _round(cur_ratio, 6)
            metrics[f"{canonical}_revenue_ratio_prior"] = _round(prior_ratio, 6)
            metrics[f"{canonical}_revenue_ratio_yoy_delta"] = _round(delta, 6)
            if delta is not None:
                available += 1
                pass_flags.append(delta <= MAX_WORKING_CAPITAL_RATIO_DETERIORATION)

        if available == 0:
            metrics["working_capital_status"] = "missing_receivables_inventory_pairs"
            metrics["working_capital_discipline_pass_v1"] = False
        elif all(pass_flags):
            metrics["working_capital_discipline_pass_v1"] = True
        else:
            metrics["working_capital_status"] = "working_capital_ratio_deteriorated"
            metrics["working_capital_discipline_pass_v1"] = False
        return metrics


def _working_capital_index_for_candidates(
    candidates: list[dict[str, Any]],
) -> CompanyfactsWorkingCapitalIndex:
    tickers = sorted({str(row.get("ticker") or "").upper() for row in candidates})
    max_filed = max((_date10(row.get("date") or row.get("signal_date")) for row in candidates), default="")
    rows = _source_base()._load_companyfacts_rows(max_filed=max_filed, tickers=tickers)
    return CompanyfactsWorkingCapitalIndex(rows)


def _working_capital_bucket(context: dict[str, Any]) -> str:
    if not context.get("working_capital_discipline_pass_v1"):
        return str(context.get("working_capital_status") or "failed")
    receivables_delta = _float(context.get("receivables_revenue_ratio_yoy_delta"))
    inventory_delta = _float(context.get("inventory_revenue_ratio_yoy_delta"))
    positive_deltas = [value for value in (receivables_delta, inventory_delta) if value is not None and value > 0]
    if not positive_deltas:
        return "clean_or_improving"
    if max(positive_deltas) <= 0.02:
        return "mild_deterioration_lte_2pp"
    return "controlled_deterioration_lte_5pp"


def _working_capital_scalar(context: dict[str, Any]) -> float:
    if context.get("working_capital_discipline_pass_v1"):
        return WORKING_CAPITAL_NOTIONAL_SCALAR
    return 1.0


def _select_working_capital_supported_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = _base()
    governor = _governor()
    label = governor._window_label_for_candidates(candidates)
    balance_sheet_index = prev._balance_sheet_index_for_candidates(candidates)
    working_capital_index = _working_capital_index_for_candidates(candidates)
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
    bucket_counts: Counter[str] = Counter()

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
        working_capital_context = working_capital_index.current_context(ticker, signal_date)
        working_capital_scalar = _working_capital_scalar(working_capital_context)
        notional_scalar_before_working_capital = (
            ticker_profit_scalar
            * global_drawdown_scalar
            * low_volume_scalar
            * filing_recency_scalar
            * balance_sheet_scalar
        )
        notional_scalar = notional_scalar_before_working_capital * working_capital_scalar

        filing_age = prev.prev._operating_income_filing_age_days(row)
        balance_bucket = prev._liability_assets_bucket(balance_context.get("liabilities_assets_ratio"))
        working_bucket = _working_capital_bucket(working_capital_context)
        bucket_counts[working_bucket] += 1
        status_counts[str(working_capital_context.get("working_capital_status") or "unknown")] += 1

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
        if working_capital_scalar > 1.0:
            audit["working_capital_supported"] += 1
            supported_ticker_counts[ticker] += 1
        if ticker_profit_scalar < 1.0 and global_drawdown_scalar < 1.0:
            audit["both_governor_scalars_applied"] += 1

        base_notional = float(trade.get("paper_notional_usd") or base.BASE_NOTIONAL_USD)
        pnl_pct_net = float(trade.get("pnl_pct_net") or 0.0)
        pre_working_capital_notional = base_notional * notional_scalar_before_working_capital
        supported_notional = base_notional * notional_scalar
        pre_working_capital_pnl = pre_working_capital_notional * pnl_pct_net
        supported_pnl = supported_notional * pnl_pct_net
        if working_capital_scalar > 1.0:
            support_pnl_delta_by_ticker[ticker] += supported_pnl - pre_working_capital_pnl

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
            "working_capital_rule_version": RULE_VERSION,
            "working_capital_trade_enabled": False,
            "working_capital_alters_orders": False,
            "working_capital_bucket": working_bucket,
            "working_capital_notional_scalar": working_capital_scalar,
            **working_capital_context,
            "closed_ledger_notional_scalar": _round(notional_scalar, 6),
            "global_closed_pnl_before_entry": _round(cumulative_closed_pnl, 2),
            "global_closed_peak_pnl_before_entry": _round(peak_closed_pnl, 2),
            "global_closed_drawdown_before_entry": _round(closed_drawdown, 2),
            "ticker_closed_pnl_before_entry": _round(ticker_closed_pnl[ticker], 2),
            "paper_notional_usd": _round(supported_notional, 2),
            "pnl": _round(supported_pnl, 2),
            "pnl_without_working_capital_support": _round(pre_working_capital_pnl, 2),
            "working_capital_support_pnl_delta": _round(supported_pnl - pre_working_capital_pnl, 2),
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

    WORKING_CAPITAL_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "max_working_capital_ratio_deterioration": MAX_WORKING_CAPITAL_RATIO_DETERIORATION,
        "working_capital_notional_scalar": WORKING_CAPITAL_NOTIONAL_SCALAR,
        "input_candidates": len(candidates),
        "selected_trades": len(selected),
        "filtered_candidates": len(filtered),
        "working_capital_supported": int(audit.get("working_capital_supported", 0)),
        "low_liability_supported": int(audit.get("low_liability_supported", 0)),
        "filing_recency_supported": int(audit.get("filing_recency_supported", 0)),
        "low_volume_supported": int(audit.get("low_volume_supported", 0)),
        "final_closed_pnl": _round(cumulative_closed_pnl, 2),
        "max_closed_drawdown_seen_usd": _round(max_closed_drawdown_seen, 2),
        "selected_unique_tickers": len({str(row.get("ticker") or "").upper() for row in selected}),
        "selected_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in selected).items())
        ),
        "working_capital_status_counts": dict(sorted(status_counts.items())),
        "working_capital_bucket_counts": dict(sorted(bucket_counts.items())),
        "working_capital_supported_ticker_counts": dict(sorted(supported_ticker_counts.items())),
        "working_capital_support_pnl_delta_by_ticker": {
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
        "accepted_candidate_fundamental_growth_rs_working_capital_discipline_support"
        if gate4_passed
        else "rejected_fundamental_growth_rs_working_capital_discipline_support"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / capital allocation: within the accepted Companyfacts "
        "operating-profit + RS paper source, stable receivables/revenue and "
        "inventory/revenue ratios are a free SEC working-capital quality field. "
        "A small default-off paper notional support should favor growth that is "
        "not being funded by deteriorating collections or inventory build."
    )
    payload["change_type"] = "fundamental_growth_rs_working_capital_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 18
    payload["nearby_prior_experiments"] = [
        "exp-20260528-004",
        "exp-20260528-006",
        "exp-20260528-008",
        "exp-20260528-012",
        "exp-20260528-015",
        "exp-20260528-016",
        "exp-20260528-017",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_sec_companyfacts_working_capital_quality_field"
    payload["parameters"]["working_capital_discipline_support"] = {
        "max_receivables_or_inventory_revenue_ratio_yoy_deterioration": MAX_WORKING_CAPITAL_RATIO_DETERIORATION,
        "paper_notional_scalar": WORKING_CAPITAL_NOTIONAL_SCALAR,
        "applies_to": (
            "already selected exp-20260528-017 governed default-off paper trades "
            "after daily top-1 selection"
        ),
        "uses_future_data": False,
        "production_visible_field": (
            "latest and prior-year same-quarter revenue, receivables, and inventory "
            "from SEC Companyfacts with filed <= signal_date"
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
            "candidate_pool / capital allocation alpha: PIT receivables/revenue "
            "and inventory/revenue discipline is a distinct free SEC quality field "
            "for the accepted Companyfacts+RS paper pool."
        ),
        "2_history_check": {
            "exp-20260528-017": "Accepted low-liability support on the current governed Companyfacts+RS baseline.",
            "exp-20260528-016": "Accepted filing-recency support.",
            "exp-20260528-015": "Accepted low-volume participation support.",
            "exp-20260528-012": "Gross-margin expansion failed versus the accepted governed baseline.",
            "exp-20260528-006": "Cash-conversion quality failed drawdown/concentration.",
            "current_difference": (
                "This run does not retune growth, RS, margin, cash-flow, volume, "
                "filing-age, liabilities/assets, top-N, hold, or governor thresholds; "
                "it tests a working-capital discipline field."
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
            "exp_20260528_019_fundamental_growth_rs_working_capital_discipline.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "revenue, receivables, and inventory facts filed <= signal_date",
    ]
    payload["gate2"]["note"] = (
        "The only new field is working-capital discipline, computed from "
        "Companyfacts revenue, receivables, and inventory facts with filed dates "
        "<= signal_date. Paper entry remains next-open and the closed-ledger "
        "governor uses only rows with exit_date < entry_date."
    )
    payload["gate3"]["candidate_pool_changed"] = False
    payload["gate3"]["note"] = (
        "No core filter, live entry rule, or paper candidate filter was added. "
        "The rule scales default-off paper notional after selected candidate "
        "selection, so core survival is unchanged."
    )
    payload["working_capital_audit"] = WORKING_CAPITAL_AUDIT
    payload["reference_accepted_low_liability_exp017_comparison"] = reference_comparison
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, Kova, state-surface, "
        "broad-market, VCP/VBB threshold retunes, Companyfacts growth/RS/top-N/hold, "
        "cash-conversion, gross-margin, low-volume threshold, filing-recency "
        "threshold, liabilities/assets threshold, and closed-ledger governor retunes. "
        "This run tests only a new SEC working-capital field on the accepted "
        "Companyfacts+RS paper source."
    )
    payload["interpretation"] = (
        "The working-capital discipline support cleared Gate 4 on top of the "
        "accepted exp-20260528-017 baseline. It is a candidate for a shared "
        "default-off adapter update with parity tests; it is not live capital activation."
        if gate4_passed
        else (
            "The working-capital discipline support did not clear Gate 4. Do not "
            "promote it or retry nearby receivables/inventory thresholds or scalars "
            "on the frozen windows without forward rows or a materially new quality field."
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
                    "A retained positive result would require the same working-capital "
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
        "# exp-20260528-019 Fundamental Growth + RS Working-Capital Discipline",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: apply a 1.05x paper-notional support scalar to "
            "already selected governed Companyfacts+RS paper candidates whose "
            "PIT receivables/revenue and inventory/revenue ratios do not deteriorate "
            "by more than 5 percentage points versus the prior-year same quarter."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Working-capital supported |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _base().WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["working_capital_audit"].get(label, {})
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
                supported=audit.get("working_capital_supported"),
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
            "## Working-Capital Audit",
            "",
            "```json",
            json.dumps(payload["working_capital_audit"], indent=2, sort_keys=True),
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
        "title": "Fundamental growth + RS working-capital discipline",
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
                    "working_capital_audit": payload["working_capital_audit"],
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
