"""exp-20260528-006: Companyfacts+RS cash-conversion quality scout.

Alpha search follow-up to exp-20260527-017. This keeps the PIT SEC
Companyfacts growth + OHLCV RS candidate source fixed, then changes one
source-quality variable: candidates must have a latest comparable-period
operating cash flow fact that is positive and covers reported net income.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260527_017_fundamental_growth_rs_candidate_pool as prev


EXPERIMENT_ID = "exp-20260528-006"
STEM = "fundamental_growth_rs_cash_conversion_quality"
TRIAL_FAMILY = "fundamental_growth_rs_cash_conversion_quality"
CHANGED_VARIABLE = "fundamental_growth_rs_cash_conversion_quality_v1"
RULE_VERSION = "fundamental_growth_rs_cash_conversion_quality_v1"

MIN_CASH_CONVERSION_RATIO = 0.75
MAX_DURATION_MISMATCH_DAYS = 20

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REFERENCE_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260528-004.json"

CASH_QUALITY_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
CASH_INDEX: "CompanyfactsCashConversionIndex | None" = None


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
    prev.FUNDAMENTAL_RS_AUDIT.clear()
    prev.FACT_INDEX = None
    global CASH_INDEX
    CASH_INDEX = None
    prev._configure_base_module()
    prev.base._candidate_rows_for_window = _candidate_rows_for_window


def _window_label(cfg: dict[str, str]) -> str:
    for label, window_cfg in prev.base.WINDOWS.items():
        if window_cfg is cfg:
            return label
    return str(cfg.get("start") or "unknown")


def _fact_value(row: dict[str, Any] | None) -> float | None:
    if row is None:
        return None
    return prev._float(row.get("value"))


def _duration(row: dict[str, Any] | None) -> float | None:
    if row is None:
        return None
    return prev._float(row.get("duration_days"))


def _cash_fact_sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
    duration = _duration(row)
    duration_penalty = -abs((duration or 999.0) - 91.0)
    form = str(row.get("form") or "").upper()
    form_priority = 2 if form == "10-Q" else 1 if form == "10-K" else 0
    return (
        str(row.get("end") or ""),
        str(row.get("filed") or "")[:10],
        form_priority,
        duration_penalty,
    )


class CompanyfactsCashConversionIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = str(raw.get("filed") or "")[:10]
            value = prev._float(raw.get("value"))
            if canonical not in {"operating_cash_flow", "net_income"}:
                continue
            if not ticker or not filed or value is None:
                continue
            duration = _duration(raw)
            if duration is None or duration < 60 or duration > 400:
                continue
            by_key[(ticker, canonical)].append(
                {
                    **raw,
                    "ticker": ticker,
                    "canonical": canonical,
                    "filed": filed,
                    "value": value,
                    "duration_days_float": duration,
                    "fy_int": prev._int(raw.get("fy")),
                    "fp_norm": str(raw.get("fp") or "").upper(),
                }
            )
        for bucket in by_key.values():
            bucket.sort(key=_cash_fact_sort_key)
        self.by_key = by_key

    def current_fact(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any] | None:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        return rows[-1] if rows else None

    def matching_net_income(
        self,
        ticker: str,
        cash_flow_fact: dict[str, Any] | None,
        asof_date: str,
    ) -> dict[str, Any] | None:
        if cash_flow_fact is None:
            return None
        ticker = ticker.upper()
        target_end = str(cash_flow_fact.get("end") or "")
        target_duration = _duration(cash_flow_fact)
        candidates = [
            row
            for row in self.by_key.get((ticker, "net_income"), [])
            if str(row.get("filed") or "")[:10] <= asof_date
            and str(row.get("end") or "") == target_end
        ]
        if target_duration is not None:
            candidates = [
                row
                for row in candidates
                if _duration(row) is not None
                and abs(float(_duration(row)) - target_duration) <= MAX_DURATION_MISMATCH_DAYS
            ]
        if candidates:
            return sorted(candidates, key=_cash_fact_sort_key)[-1]
        return self.current_fact(ticker, "net_income", asof_date)

    def cash_conversion_quality(self, ticker: str, asof_date: str) -> dict[str, Any]:
        cash_flow = self.current_fact(ticker, "operating_cash_flow", asof_date)
        net_income = self.matching_net_income(ticker, cash_flow, asof_date)
        ocf_value = _fact_value(cash_flow)
        ni_value = _fact_value(net_income)
        ocf_duration = _duration(cash_flow)
        ni_duration = _duration(net_income)
        duration_mismatch = None
        if ocf_duration is not None and ni_duration is not None:
            duration_mismatch = abs(ocf_duration - ni_duration)
        ratio = None
        if ocf_value is not None and ni_value is not None and ni_value > 0:
            ratio = ocf_value / ni_value
        quality_pass = (
            ocf_value is not None
            and ni_value is not None
            and ocf_value > 0.0
            and ni_value > 0.0
            and ratio is not None
            and ratio >= MIN_CASH_CONVERSION_RATIO
            and (
                duration_mismatch is None
                or duration_mismatch <= MAX_DURATION_MISMATCH_DAYS
            )
        )
        if cash_flow is None:
            status = "missing_operating_cash_flow_fact"
        elif net_income is None:
            status = "missing_net_income_fact"
        elif ocf_value is None or ni_value is None:
            status = "missing_cash_or_income_value"
        elif ocf_value <= 0:
            status = "non_positive_operating_cash_flow"
        elif ni_value <= 0:
            status = "non_positive_net_income"
        elif duration_mismatch is not None and duration_mismatch > MAX_DURATION_MISMATCH_DAYS:
            status = "duration_mismatch"
        elif ratio is not None and ratio < MIN_CASH_CONVERSION_RATIO:
            status = "weak_cash_conversion"
        else:
            status = "ok"
        return {
            "cash_conversion_quality_rule_version": RULE_VERSION,
            "cash_conversion_quality_known_at": "SEC Companyfacts filed date <= signal_date",
            "cash_conversion_quality_trade_enabled": False,
            "cash_conversion_quality_alters_orders": False,
            "operating_cash_flow_status": "ok" if cash_flow else "missing_operating_cash_flow_fact",
            "operating_cash_flow_current_value": prev.base._round(ocf_value, 6),
            "operating_cash_flow_current_filed": cash_flow.get("filed") if cash_flow else None,
            "operating_cash_flow_current_period_end": cash_flow.get("end") if cash_flow else None,
            "operating_cash_flow_current_form": cash_flow.get("form") if cash_flow else None,
            "operating_cash_flow_duration_days": prev.base._round(ocf_duration, 2),
            "cash_conversion_net_income_status": "ok" if net_income else "missing_net_income_fact",
            "cash_conversion_net_income_value": prev.base._round(ni_value, 6),
            "cash_conversion_net_income_filed": net_income.get("filed") if net_income else None,
            "cash_conversion_net_income_period_end": net_income.get("end") if net_income else None,
            "cash_conversion_net_income_form": net_income.get("form") if net_income else None,
            "cash_conversion_net_income_duration_days": prev.base._round(ni_duration, 2),
            "cash_conversion_duration_mismatch_days": prev.base._round(duration_mismatch, 2),
            "cash_conversion_ratio": prev.base._round(ratio, 6),
            "cash_conversion_quality_status": status,
            "cash_conversion_quality_pass_v1": quality_pass,
        }


def _candidate_tickers(snapshot: dict[str, list[dict[str, Any]]], universe: list[str]) -> list[str]:
    out: list[str] = []
    for ticker in sorted(set(universe).intersection(snapshot).difference(prev.EXCLUDED_TICKERS)):
        sector = prev.ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown")
        if sector not in {"Unknown", "ETF", "Commodities"}:
            out.append(ticker)
    return out


def _get_cash_index(candidate_tickers: list[str]) -> CompanyfactsCashConversionIndex:
    global CASH_INDEX
    if CASH_INDEX is None:
        max_window_end = max(cfg["end"] for cfg in prev.base.WINDOWS.values())
        CASH_INDEX = CompanyfactsCashConversionIndex(
            prev._load_companyfacts_rows(max_filed=max_window_end, tickers=candidate_tickers)
        )
    return CASH_INDEX


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = prev._candidate_rows_for_window(snapshot, cfg, universe, before_result)
    cash_index = _get_cash_index(_candidate_tickers(snapshot, universe))
    retained: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        quality = cash_index.cash_conversion_quality(str(row.get("ticker") or ""), str(row["date"]))
        merged = {
            **row,
            **quality,
            "selection_rule_version": RULE_VERSION,
            "rule_version": RULE_VERSION,
        }
        if quality["cash_conversion_quality_pass_v1"]:
            retained.append(merged)
        else:
            filtered.append(
                {
                    **merged,
                    "filter_reason": "missing_or_weak_cash_conversion_quality",
                }
            )

    label = _window_label(cfg)
    prev.FUNDAMENTAL_RS_AUDIT[label]["cash_conversion_quality_candidates"] = len(retained)
    prev.FUNDAMENTAL_RS_AUDIT[label]["cash_conversion_quality_days"] = len(
        {row["date"] for row in retained}
    )
    prev.FUNDAMENTAL_RS_AUDIT[label]["cash_conversion_quality_tickers"] = len(
        {row["ticker"] for row in retained}
    )
    CASH_QUALITY_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "input_candidates": len(rows),
        "retained_candidates": len(retained),
        "filtered_candidates": len(filtered),
        "retained_days": len({row["date"] for row in retained}),
        "retained_unique_tickers": len({row["ticker"] for row in retained}),
        "filtered_unique_tickers": len({row["ticker"] for row in filtered}),
        "cash_conversion_status_counts": dict(
            sorted(
                Counter(
                    str(row.get("cash_conversion_quality_status") or "unknown")
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
        "expected_value_score_sum": prev.base._round(ev, 6),
        "total_pnl_sum": prev.base._round(pnl, 2),
        "max_drawdown_pct_max": prev.base._round(dd, 6),
        "trade_count_sum": trades,
    }


def _reference_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    if not REFERENCE_JSON.exists():
        return {"available": False, "reason": "missing_exp_20260528_004_reference"}
    reference = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))
    ref_after = reference.get("after_metrics") or {}
    after = payload.get("after_metrics") or {}
    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label in prev.base.WINDOWS:
        ref = ref_after.get(label) or {}
        cur = after.get(label) or {}
        by_window[label] = {
            "expected_value_score_delta": prev.base._round(
                float(cur.get("expected_value_score") or 0.0)
                - float(ref.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_delta": prev.base._round(
                float(cur.get("total_pnl") or 0.0) - float(ref.get("total_pnl") or 0.0),
                2,
            ),
            "max_drawdown_pct_delta": prev.base._round(
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
        "by_window_delta_after_vs_operating_profit_quality": by_window,
        "aggregate_delta_after_vs_operating_profit_quality": {
            "expected_value_score_delta_sum": prev.base._round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": prev.base._round(
                cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"], 2
            ),
            "max_drawdown_pct_delta_max": prev.base._round(
                cur_agg["max_drawdown_pct_max"] - ref_agg["max_drawdown_pct_max"],
                6,
            ),
        },
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_fundamental_growth_rs_cash_conversion_quality"
        if gate4_passed
        else "rejected_fundamental_growth_rs_cash_conversion_quality"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / entry: exp-20260527-017 and exp-20260528-004 showed "
        "large gross alpha from PIT SEC Companyfacts growth plus OHLCV RS but "
        "failed drawdown and concentration. A cash-conversion quality field "
        "should prefer growth candidates whose reported net income is supported "
        "by operating cash flow, potentially reducing fragile high-RS concentration."
    )
    payload["change_type"] = "fundamental_growth_rs_cash_conversion_quality_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 10
    payload["nearby_prior_experiments"] = [
        "exp-20260527-017",
        "exp-20260527-018",
        "exp-20260527-019",
        "exp-20260527-020",
        "exp-20260527-023",
        "exp-20260527-903",
        "exp-20260528-004",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_cash_conversion_quality_field"
    payload["parameters"]["cash_conversion_quality"] = {
        "operating_cash_flow_required_gt": 0.0,
        "net_income_required_gt": 0.0,
        "min_operating_cash_flow_to_net_income_ratio": MIN_CASH_CONVERSION_RATIO,
        "max_duration_mismatch_days": MAX_DURATION_MISMATCH_DAYS,
        "applies_to": "exp-20260527-017 default-off paper candidate rows before daily top-1 selection",
        "uses_future_data": False,
        "production_visible_field": "PIT SEC Companyfacts latest operating_cash_flow and comparable net_income filed <= signal_date",
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "skip unless cash_conversion_quality_pass_v1",
        "fundamental_growth_rs_score_v1 desc",
        "rs_proxy_score_v1 desc",
        "fundamental_growth_points_v1 desc",
        "avg_dollar_volume_20 desc",
        "ticker asc",
    ]
    payload["parameters"]["locked_variables"] = [
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
        "paper notional",
        "paper hold period",
    ]
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry alpha: cash-conversion quality is a distinct "
            "free SEC source-quality field for the Companyfacts+RS paper pool."
        ),
        "2_history_check": {
            "exp-20260527-017": "Gross edge was large but failed old_thin drawdown and APP concentration.",
            "exp-20260527-018": "Ticker cooldown reduced concentration but regressed late_strong and drawdown.",
            "exp-20260527-020": "Dual EPS+revenue growth kept gross EV but failed drawdown/concentration.",
            "exp-20260527-903": "Sector exposure cap passed concentration but failed drawdown.",
            "exp-20260528-004": "Positive operating income improved all windows but still failed drawdown and APP concentration.",
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
            "exp_20260528_006_fundamental_growth_rs_cash_conversion_quality.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "PIT operating_cash_flow current comparable fact filed <= signal_date",
        "PIT net_income current comparable fact filed <= signal_date",
    ]
    payload["gate2"]["note"] = (
        "SEC cash-flow and net-income rows are filtered by filed <= signal_date. "
        "RS, trend, liquidity, and returns use signal-date or trailing OHLCV only. "
        "Paper entry occurs at the next open; no LLM, news, hidden event field, "
        "or future bar is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The cash-conversion quality "
        "condition only changes default-off paper sleeve selection, so core survival is unchanged."
    )
    payload["cash_conversion_quality_audit"] = CASH_QUALITY_AUDIT
    payload["fundamental_growth_rs_audit"] = prev.FUNDAMENTAL_RS_AUDIT
    payload["reference_operating_profit_exp004_comparison"] = _reference_comparison(payload)
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, and Kova intraday because "
        "recent records show sparse or readiness-blocked attribution. Skipped VCP, "
        "VBB, state-surface, broad-market, and nearby Companyfacts+RS growth, RS, "
        "top-N, fixed-notional, cooldown, extension, QQQ, sector-exposure, and "
        "one-line operating-profit variants per playbook freeze guidance. This run "
        "tests cash conversion quality."
    )
    payload["interpretation"] = (
        "The cash-conversion Companyfacts+RS sleeve cleared Gate 4 as a replay-only "
        "lead. It is still not live capital; promotion requires a shared default-off "
        "paper adapter, daily report exposure, forward replacement-value ledger, "
        "and parity tests."
        if gate4_passed
        else (
            "The cash-conversion Companyfacts+RS sleeve did not clear Gate 4. Do not "
            "promote it or retry nearby Companyfacts+RS cash-flow, profitability, "
            "growth, RS, top-N, cooldown, extension, QQQ, or sector-exposure thresholds "
            "on the frozen windows without forward rows or a materially new field."
        )
    )
    payload["next_evidence_needed"] = (
        "If positive, implement only as shared default-off paper before activation; "
        "if rejected, require forward rows or a new source-quality field outside "
        "basic growth, RS, operating-profit, and cash-conversion variants."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper adapter, "
        "daily report exposure, forward replacement-value ledger, and parity tests "
        "before any live/default behavior changes."
    )
    payload["related_files"] = [
        prev.base._repo_rel(Path(__file__)),
        prev.base._repo_rel(OUT_JSON),
        prev.base._repo_rel(LOG_JSON),
        prev.base._repo_rel(TICKET_JSON),
        prev.base._repo_rel(DOC_TICKET_JSON),
        prev.base._repo_rel(ARTIFACT_MD),
        prev.base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260528-006 Fundamental Growth + RS Cash-Conversion Quality",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: require latest PIT operating cash flow to be positive "
            "and at least 75% of comparable-period net income inside the "
            "exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper source."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Retained candidates | Filtered candidates | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prev.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["cash_conversion_quality_audit"].get(label, {})
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
            "## Cash-Conversion Quality Audit",
            "",
            "```json",
            json.dumps(payload["cash_conversion_quality_audit"], indent=2, sort_keys=True),
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
                "core entry, ranking, sizing, or exit behavior changed."
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
        "title": "Fundamental growth + RS cash-conversion quality scout",
        "status": payload["decision"],
        "lane": "alpha_search",
        "updated_at": payload["timestamp"],
        "artifacts": {
            "json": prev.base._repo_rel(OUT_JSON),
            "log": prev.base._repo_rel(LOG_JSON),
            "report": prev.base._repo_rel(ARTIFACT_MD),
        },
    }
    prev.base._write_json(OUT_JSON, payload)
    prev.base._write_json(LOG_JSON, payload)
    prev.base._write_json(TICKET_JSON, ticket)
    prev.base._write_json(DOC_TICKET_JSON, ticket)
    prev.base._write_text(ARTIFACT_MD, _build_report(payload))
    prev.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _update_payload(prev.base._build_payload())
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
