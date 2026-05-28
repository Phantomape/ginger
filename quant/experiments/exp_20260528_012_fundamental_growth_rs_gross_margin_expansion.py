"""exp-20260528-012: Companyfacts+RS gross-margin expansion scout.

Alpha search follow-up to the accepted Companyfacts operating-profit + RS
paper lead. This keeps the PIT SEC Companyfacts growth + operating-profit
quality + OHLCV RS candidate source and the accepted closed-ledger governor
fixed, then changes one source-quality variable: require same-quarter gross
margin to be non-declining year over year.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260528_008_operating_profit_quality_closed_ledger_governor as governor
import exp_20260528_004_fundamental_growth_rs_operating_profit_quality as source


EXPERIMENT_ID = "exp-20260528-012"
STEM = "fundamental_growth_rs_gross_margin_expansion"
TRIAL_FAMILY = "fundamental_growth_rs_gross_margin_expansion_quality"
CHANGED_VARIABLE = "fundamental_growth_rs_gross_margin_expansion_quality_v1"
RULE_VERSION = "fundamental_growth_rs_gross_margin_expansion_quality_v1"

MIN_GROSS_MARGIN_DELTA = 0.0

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

GROSS_MARGIN_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
GROSS_MARGIN_INDEX: "CompanyfactsGrossMarginIndex | None" = None


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
    global GROSS_MARGIN_INDEX
    GROSS_MARGIN_INDEX = None
    source._configure_modules()
    source.prev.base._candidate_rows_for_window = _candidate_rows_for_window
    source.prev.base._select_paper_trades = governor._select_governed_paper_trades


def _fact_value(row: dict[str, Any] | None) -> float | None:
    if row is None:
        return None
    return source.prev._float(row.get("value"))


class CompanyfactsGrossMarginIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = str(raw.get("filed") or "")[:10]
            value = source.prev._float(raw.get("value"))
            if canonical not in {"gross_profit", "revenue"}:
                continue
            if not ticker or not filed or value is None or not source.prev._is_quarterly_fact(raw):
                continue
            by_key[(ticker, canonical)].append(
                {
                    **raw,
                    "ticker": ticker,
                    "canonical": canonical,
                    "filed": filed,
                    "value": value,
                    "fy_int": source.prev._int(raw.get("fy")),
                    "fp_norm": str(raw.get("fp") or "").upper(),
                }
            )
        for bucket in by_key.values():
            bucket.sort(key=source.prev._fact_sort_key)
        self.by_key = by_key

    def latest_fact(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any] | None:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if str(row.get("filed") or "")[:10] <= asof_date
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
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        if end:
            rows = [row for row in rows if str(row.get("end") or "") == end]
        if fy is not None:
            rows = [row for row in rows if row.get("fy_int") == fy]
        if fp:
            rows = [row for row in rows if row.get("fp_norm") == fp]
        return rows[-1] if rows else None

    def gross_margin_quality(self, ticker: str, asof_date: str) -> dict[str, Any]:
        ticker = ticker.upper()
        current_gross = self.latest_fact(ticker, "gross_profit", asof_date)
        current_revenue = None
        prior_gross = None
        prior_revenue = None
        if current_gross is not None:
            current_revenue = self.matching_fact(
                ticker,
                "revenue",
                asof_date,
                end=str(current_gross.get("end") or ""),
            )
            fy = current_gross.get("fy_int")
            fp = current_gross.get("fp_norm")
            if fy is not None and fp:
                prior_gross = self.matching_fact(
                    ticker,
                    "gross_profit",
                    asof_date,
                    fy=int(fy) - 1,
                    fp=str(fp),
                )
                if prior_gross is not None:
                    prior_revenue = self.matching_fact(
                        ticker,
                        "revenue",
                        asof_date,
                        end=str(prior_gross.get("end") or ""),
                    )

        current_gross_value = _fact_value(current_gross)
        current_revenue_value = _fact_value(current_revenue)
        prior_gross_value = _fact_value(prior_gross)
        prior_revenue_value = _fact_value(prior_revenue)

        current_margin = None
        if current_gross_value is not None and current_revenue_value and current_revenue_value > 0:
            current_margin = current_gross_value / current_revenue_value
        prior_margin = None
        if prior_gross_value is not None and prior_revenue_value and prior_revenue_value > 0:
            prior_margin = prior_gross_value / prior_revenue_value
        margin_delta = None
        if current_margin is not None and prior_margin is not None:
            margin_delta = current_margin - prior_margin

        pass_v1 = (
            current_margin is not None
            and prior_margin is not None
            and current_margin > 0.0
            and margin_delta is not None
            and margin_delta >= MIN_GROSS_MARGIN_DELTA
        )
        if current_gross is None:
            status = "missing_current_gross_profit"
        elif current_revenue is None:
            status = "missing_current_revenue"
        elif prior_gross is None:
            status = "missing_prior_gross_profit_same_quarter"
        elif prior_revenue is None:
            status = "missing_prior_revenue_same_quarter"
        elif current_margin is None or prior_margin is None:
            status = "missing_margin_denominator"
        elif margin_delta is not None and margin_delta < MIN_GROSS_MARGIN_DELTA:
            status = "gross_margin_declined"
        else:
            status = "ok"

        return {
            "gross_margin_quality_rule_version": RULE_VERSION,
            "gross_margin_quality_known_at": "SEC Companyfacts filed date <= signal_date",
            "gross_margin_quality_trade_enabled": False,
            "gross_margin_quality_alters_orders": False,
            "gross_margin_quality_status": status,
            "gross_margin_current": source.prev.base._round(current_margin, 6),
            "gross_margin_prior_year_same_quarter": source.prev.base._round(prior_margin, 6),
            "gross_margin_yoy_delta": source.prev.base._round(margin_delta, 6),
            "gross_margin_delta_min": MIN_GROSS_MARGIN_DELTA,
            "gross_margin_expansion_pass_v1": pass_v1,
            "gross_profit_current_value": source.prev.base._round(current_gross_value, 6),
            "gross_profit_current_filed": current_gross.get("filed") if current_gross else None,
            "gross_profit_current_period_end": current_gross.get("end") if current_gross else None,
            "gross_profit_prior_value": source.prev.base._round(prior_gross_value, 6),
            "gross_profit_prior_filed": prior_gross.get("filed") if prior_gross else None,
            "gross_profit_prior_period_end": prior_gross.get("end") if prior_gross else None,
        }


def _get_margin_index(candidate_tickers: list[str]) -> CompanyfactsGrossMarginIndex:
    global GROSS_MARGIN_INDEX
    if GROSS_MARGIN_INDEX is None:
        max_window_end = max(cfg["end"] for cfg in source.prev.base.WINDOWS.values())
        GROSS_MARGIN_INDEX = CompanyfactsGrossMarginIndex(
            source.prev._load_companyfacts_rows(max_filed=max_window_end, tickers=candidate_tickers)
        )
    return GROSS_MARGIN_INDEX


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = source._candidate_rows_for_window(snapshot, cfg, universe, before_result)
    margin_index = _get_margin_index(source._candidate_tickers(snapshot, universe))
    retained: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        quality = margin_index.gross_margin_quality(str(row.get("ticker") or ""), str(row["date"]))
        merged = {
            **row,
            **quality,
            "selection_rule_version": RULE_VERSION,
            "rule_version": RULE_VERSION,
        }
        if quality["gross_margin_expansion_pass_v1"]:
            retained.append(merged)
        else:
            filtered.append({**merged, "filter_reason": "missing_or_declining_gross_margin"})

    label = source._window_label(cfg)
    source.prev.FUNDAMENTAL_RS_AUDIT[label]["gross_margin_expansion_candidates"] = len(retained)
    source.prev.FUNDAMENTAL_RS_AUDIT[label]["gross_margin_expansion_days"] = len(
        {row["date"] for row in retained}
    )
    source.prev.FUNDAMENTAL_RS_AUDIT[label]["gross_margin_expansion_tickers"] = len(
        {row["ticker"] for row in retained}
    )
    GROSS_MARGIN_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "input_candidates": len(rows),
        "retained_candidates": len(retained),
        "filtered_candidates": len(filtered),
        "retained_days": len({row["date"] for row in retained}),
        "retained_unique_tickers": len({row["ticker"] for row in retained}),
        "filtered_unique_tickers": len({row["ticker"] for row in filtered}),
        "gross_margin_status_counts": dict(
            sorted(
                Counter(
                    str(row.get("gross_margin_quality_status") or "unknown")
                    for row in retained + filtered
                ).items()
            )
        ),
        "retained_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in retained).items())
        ),
        "filtered_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in filtered).items())
        ),
    }
    return retained


def _aggregate_metrics(metrics_by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev = sum(float(row.get("expected_value_score") or 0.0) for row in metrics_by_window.values())
    pnl = sum(float(row.get("total_pnl") or 0.0) for row in metrics_by_window.values())
    dd = max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics_by_window.values())
    trades = sum(int(row.get("trade_count") or 0) for row in metrics_by_window.values())
    return {
        "expected_value_score_sum": source.prev.base._round(ev, 6),
        "total_pnl_sum": source.prev.base._round(pnl, 2),
        "max_drawdown_pct_max": source.prev.base._round(dd, 6),
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
    for label in source.prev.base.WINDOWS:
        ref = ref_after.get(label) or {}
        cur = after.get(label) or {}
        by_window[label] = {
            "expected_value_score_delta": source.prev.base._round(
                float(cur.get("expected_value_score") or 0.0)
                - float(ref.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_delta": source.prev.base._round(
                float(cur.get("total_pnl") or 0.0) - float(ref.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_pct_delta": source.prev.base._round(
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
            "expected_value_score_delta_sum": source.prev.base._round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": source.prev.base._round(
                cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"],
                2,
            ),
            "max_drawdown_pct_delta_max": source.prev.base._round(
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
        "accepted_candidate_fundamental_growth_rs_gross_margin_expansion_with_governor"
        if gate4_passed
        else "rejected_fundamental_growth_rs_gross_margin_expansion"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / entry: the accepted Companyfacts operating-profit + RS "
        "paper lead still needs source-quality fields that reduce fragile growth "
        "leaders. Same-quarter gross-margin expansion is a free SEC Companyfacts "
        "field that may distinguish operating leverage from pure revenue/EPS or "
        "price momentum."
    )
    payload["change_type"] = "fundamental_growth_rs_gross_margin_expansion_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 12
    payload["nearby_prior_experiments"] = [
        "exp-20260527-017",
        "exp-20260527-020",
        "exp-20260527-903",
        "exp-20260528-004",
        "exp-20260528-006",
        "exp-20260528-008",
        "exp-20260528-011",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_gross_margin_expansion_quality_field"
    payload["parameters"]["gross_margin_expansion_quality"] = {
        "current_gross_margin_required_gt": 0.0,
        "min_yoy_gross_margin_delta": MIN_GROSS_MARGIN_DELTA,
        "canonicals": ["gross_profit", "revenue"],
        "applies_to": "exp-20260528-004 default-off paper candidate rows before daily top-1 selection",
        "uses_future_data": False,
        "production_visible_field": "PIT SEC Companyfacts gross_profit and revenue filed <= signal_date",
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "skip unless gross_margin_expansion_pass_v1",
        "fundamental_growth_rs_score_v1 desc",
        "rs_proxy_score_v1 desc",
        "fundamental_growth_points_v1 desc",
        "avg_dollar_volume_20 desc",
        "ticker asc",
    ]
    payload["parameters"]["locked_variables"] = [
        "all exp-20260528-004 operating-profit quality logic",
        "all exp-20260527-017 Companyfacts growth thresholds",
        "all exp-20260527-017 RS proxy thresholds",
        "same-ticker cooldown disabled",
        "50d extension guard disabled",
        "sector exposure cap disabled",
        "QQQ confirmation disabled",
        "accepted exp-20260528-008 closed-ledger governor fixed unchanged",
        "core signal generation",
        "core ranking",
        "core position sizing",
        "core exits",
        "portfolio heat",
        "slot rules",
        "LLM/news replay",
        "watchlists",
        "live/default orders",
        "paper notional",
        "paper hold period",
    ]
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry alpha: gross-margin expansion is a distinct "
            "PIT SEC source-quality field for the Companyfacts+RS paper pool."
        ),
        "2_history_check": {
            "exp-20260528-004": "Positive operating income had strong gross EV but failed drawdown/concentration.",
            "exp-20260528-006": "Cash conversion had strong gross EV but failed drawdown/concentration.",
            "exp-20260528-008": "Closed-ledger governor made operating-profit quality Gate-4 pass.",
            "current_difference": "This run tests gross-margin expansion on top of the accepted governor, not growth/RS/profitability/cash-flow thresholds or a new notional governor.",
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
            "exp_20260528_012_fundamental_growth_rs_gross_margin_expansion.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "PIT gross_profit current and prior-year same-quarter facts filed <= signal_date",
        "PIT revenue current and prior-year same-quarter facts filed <= signal_date",
    ]
    payload["gate2"]["note"] = (
        "SEC gross-profit and revenue rows are filtered by filed <= signal_date. "
        "RS, trend, liquidity, and returns use signal-date or trailing OHLCV only. "
        "Paper entry occurs at the next open; no LLM, news, hidden event field, "
        "or future bar is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The gross-margin quality "
        "condition only changes default-off paper sleeve selection, so core survival is unchanged."
    )
    payload["gross_margin_quality_audit"] = GROSS_MARGIN_AUDIT
    payload["operating_profit_quality_audit"] = source.OPERATING_QUALITY_AUDIT
    payload["accepted_closed_ledger_governor_audit"] = governor.GOVERNOR_AUDIT
    payload["fundamental_growth_rs_audit"] = source.prev.FUNDAMENTAL_RS_AUDIT
    payload["reference_accepted_governed_operating_profit_exp008_comparison"] = reference_comparison
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, and Kova intraday because "
        "recent records show sparse or readiness-blocked attribution. Skipped VCP, "
        "VBB, state-surface, broad-market, and nearby Companyfacts+RS growth, RS, "
        "top-N, fixed-notional, cooldown, extension, QQQ, sector-exposure, "
        "operating-profit, cash-conversion, and closed-ledger-governor retunes. "
        "This run tests a new gross-margin expansion field while holding the accepted "
        "closed-ledger governor fixed."
    )
    payload["interpretation"] = (
        "The gross-margin expansion Companyfacts+RS sleeve cleared Gate 4 as a "
        "candidate improvement on top of the accepted closed-ledger governor. It "
        "still needs the same field in the shared default-off paper adapter with "
        "parity tests before any production behavior is retained."
        if gate4_passed
        else (
            "The gross-margin expansion Companyfacts+RS sleeve did not clear Gate 4. "
            "It either failed the core three-window gate or failed to improve on the "
            "current accepted exp-20260528-008 governed operating-profit baseline. "
            "Do not promote it or retry nearby gross-margin, profitability, cash-flow, "
            "growth, RS, top-N, cooldown, extension, QQQ, sector-exposure, or "
            "closed-ledger thresholds on the frozen windows without forward rows "
            "or a materially new field."
        )
    )
    payload["next_evidence_needed"] = (
        "Forward rows or a materially new Companyfacts source-quality field outside "
        "basic growth, operating-profit, cash-conversion, and gross-margin variants."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained positive result would require the same gross-margin field in "
        "quant/fundamental_growth_rs_paper_sleeve.py, daily report exposure, "
        "forward replacement-value ledger, and parity tests before live/default behavior changes."
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
        "# exp-20260528-012 Fundamental Growth + RS Gross-Margin Expansion",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: require current PIT same-quarter gross margin to be "
            "non-declining year over year inside the operating-profit Companyfacts "
            "+ OHLCV-RS default-off paper source."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in source.prev.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["gross_margin_quality_audit"].get(label, {})
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | "
            "{retained} | {filtered} | {tickers} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                retained=audit.get("retained_candidates"),
                filtered=audit.get("filtered_candidates"),
                tickers=audit.get("retained_unique_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{aggregate['target_trade_count_sum']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gross-Margin Quality Audit",
            "",
            "```json",
            json.dumps(payload["gross_margin_quality_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Accepted Governor Audit",
            "",
            "```json",
            json.dumps(payload["accepted_closed_ledger_governor_audit"], indent=2, sort_keys=True),
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
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed. Positive "
                "retention would require shared adapter parity before promotion."
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
        "title": "Fundamental growth + RS gross-margin expansion scout",
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
                    "gross_margin_quality_audit": payload["gross_margin_quality_audit"],
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
