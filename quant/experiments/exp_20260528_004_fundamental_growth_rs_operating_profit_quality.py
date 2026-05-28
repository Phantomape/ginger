"""exp-20260528-004: Companyfacts+RS operating-profit quality scout.

Alpha search follow-up to exp-20260527-017. This run keeps the PIT SEC
Companyfacts growth + OHLCV RS candidate source fixed, then changes one
source-quality variable: candidates must have a latest as-of quarterly
operating-income fact above zero.

No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

import exp_20260527_017_fundamental_growth_rs_candidate_pool as prev


EXPERIMENT_ID = "exp-20260528-004"
STEM = "fundamental_growth_rs_operating_profit_quality"
TRIAL_FAMILY = "fundamental_growth_rs_operating_profit_quality"
CHANGED_VARIABLE = "fundamental_growth_rs_positive_operating_income_quality_v1"
RULE_VERSION = "fundamental_growth_rs_operating_profit_quality_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REFERENCE_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260527-017.json"

OPERATING_QUALITY_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
QUALITY_INDEX: "CompanyfactsOperatingQualityIndex | None" = None


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
    global QUALITY_INDEX
    QUALITY_INDEX = None
    prev._configure_base_module()
    prev.base._candidate_rows_for_window = _candidate_rows_for_window


def _window_label(cfg: dict[str, str]) -> str:
    for label, window_cfg in prev.base.WINDOWS.items():
        if window_cfg is cfg:
            return label
    return str(cfg.get("start") or "unknown")


class CompanyfactsOperatingQualityIndex:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for raw in rows:
            ticker = str(raw.get("ticker") or "").upper()
            canonical = str(raw.get("canonical") or "")
            filed = str(raw.get("filed") or "")[:10]
            value = prev._float(raw.get("value"))
            if canonical not in {"operating_income", "revenue"}:
                continue
            if not ticker or not filed or value is None or not prev._is_quarterly_fact(raw):
                continue
            by_key[(ticker, canonical)].append(
                {
                    **raw,
                    "ticker": ticker,
                    "canonical": canonical,
                    "filed": filed,
                    "value": value,
                    "fy_int": prev._int(raw.get("fy")),
                    "fp_norm": str(raw.get("fp") or "").upper(),
                }
            )
        for bucket in by_key.values():
            bucket.sort(key=prev._fact_sort_key)
        self.by_key = by_key

    def current_fact(self, ticker: str, canonical: str, asof_date: str) -> dict[str, Any]:
        rows = [
            row
            for row in self.by_key.get((ticker.upper(), canonical), [])
            if str(row.get("filed") or "")[:10] <= asof_date
        ]
        if not rows:
            return {
                "canonical": canonical,
                "available": False,
                "status": f"missing_{canonical}_quarter_fact",
            }
        current = rows[-1]
        return {
            "canonical": canonical,
            "available": True,
            "status": "ok",
            "current_value": prev.base._round(current.get("value"), 6),
            "current_filed": current.get("filed"),
            "current_period_end": current.get("end"),
            "current_form": current.get("form"),
            "current_fp": current.get("fp_norm"),
            "current_fy": current.get("fy_int"),
            "known_at": "SEC Companyfacts filed date <= signal_date",
        }

    def operating_quality(self, ticker: str, asof_date: str) -> dict[str, Any]:
        operating_income = self.current_fact(ticker, "operating_income", asof_date)
        revenue = self.current_fact(ticker, "revenue", asof_date)
        op_value = prev._float(operating_income.get("current_value"))
        rev_value = prev._float(revenue.get("current_value"))
        margin = None
        if op_value is not None and rev_value is not None and rev_value > 0:
            margin = op_value / rev_value
        quality_pass = op_value is not None and op_value > 0.0
        return {
            "operating_profit_quality_rule_version": RULE_VERSION,
            "operating_profit_quality_known_at": "SEC Companyfacts filed date <= signal_date",
            "operating_profit_quality_trade_enabled": False,
            "operating_profit_quality_alters_orders": False,
            "operating_income_status": operating_income.get("status"),
            "operating_income_current_value": prev.base._round(op_value, 6),
            "operating_income_current_filed": operating_income.get("current_filed"),
            "operating_income_current_period_end": operating_income.get("current_period_end"),
            "operating_income_current_form": operating_income.get("current_form"),
            "operating_income_positive_pass_v1": quality_pass,
            "operating_quality_revenue_status": revenue.get("status"),
            "operating_quality_revenue_current_value": prev.base._round(rev_value, 6),
            "operating_margin_current": prev.base._round(margin, 6),
            "operating_profit_quality_pass_v1": quality_pass,
        }


def _candidate_tickers(snapshot: dict[str, list[dict[str, Any]]], universe: list[str]) -> list[str]:
    out: list[str] = []
    for ticker in sorted(set(universe).intersection(snapshot).difference(prev.EXCLUDED_TICKERS)):
        sector = prev.ohlcv_helper.SECTOR_MAP.get(ticker, "Unknown")
        if sector not in {"Unknown", "ETF", "Commodities"}:
            out.append(ticker)
    return out


def _get_quality_index(candidate_tickers: list[str]) -> CompanyfactsOperatingQualityIndex:
    global QUALITY_INDEX
    if QUALITY_INDEX is None:
        max_window_end = max(cfg["end"] for cfg in prev.base.WINDOWS.values())
        QUALITY_INDEX = CompanyfactsOperatingQualityIndex(
            prev._load_companyfacts_rows(max_filed=max_window_end, tickers=candidate_tickers)
        )
    return QUALITY_INDEX


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = prev._candidate_rows_for_window(snapshot, cfg, universe, before_result)
    quality_index = _get_quality_index(_candidate_tickers(snapshot, universe))
    retained: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        quality = quality_index.operating_quality(str(row.get("ticker") or ""), str(row["date"]))
        merged = {
            **row,
            **quality,
            "selection_rule_version": RULE_VERSION,
            "rule_version": RULE_VERSION,
        }
        if quality["operating_profit_quality_pass_v1"]:
            retained.append(merged)
        else:
            filtered.append(
                {
                    **merged,
                    "filter_reason": "missing_or_non_positive_operating_income",
                }
            )

    label = _window_label(cfg)
    prev.FUNDAMENTAL_RS_AUDIT[label]["operating_profit_quality_candidates"] = len(retained)
    prev.FUNDAMENTAL_RS_AUDIT[label]["operating_profit_quality_days"] = len(
        {row["date"] for row in retained}
    )
    prev.FUNDAMENTAL_RS_AUDIT[label]["operating_profit_quality_tickers"] = len(
        {row["ticker"] for row in retained}
    )
    OPERATING_QUALITY_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "input_candidates": len(rows),
        "retained_candidates": len(retained),
        "filtered_candidates": len(filtered),
        "retained_days": len({row["date"] for row in retained}),
        "retained_unique_tickers": len({row["ticker"] for row in retained}),
        "filtered_unique_tickers": len({row["ticker"] for row in filtered}),
        "operating_income_status_counts": dict(
            sorted(Counter(str(row.get("operating_income_status") or "unknown") for row in retained + filtered).items())
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
        return {"available": False, "reason": "missing_exp_20260527_017_reference"}
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
        "reference_experiment_id": "exp-20260527-017",
        "reference_decision": reference.get("decision"),
        "reference_gate4": reference.get("gate4"),
        "by_window_delta_after_vs_single_fact_source": by_window,
        "aggregate_delta_after_vs_single_fact_source": {
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
        "promising_replay_only_fundamental_growth_rs_operating_profit_quality"
        if gate4_passed
        else "rejected_fundamental_growth_rs_operating_profit_quality"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / entry: exp-20260527-017 showed large gross alpha from "
        "PIT SEC Companyfacts growth plus OHLCV RS, but failed drawdown and "
        "concentration. Requiring positive latest quarterly operating income is "
        "a distinct profitability-quality field outside the basic EPS/revenue "
        "growth and RS thresholds, and may keep profitable growth leaders while "
        "removing financially fragile high-RS candidates."
    )
    payload["change_type"] = "fundamental_growth_rs_operating_profit_quality_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 8
    payload["nearby_prior_experiments"] = [
        "exp-20260527-017",
        "exp-20260527-018",
        "exp-20260527-019",
        "exp-20260527-020",
        "exp-20260527-023",
        "exp-20260527-903",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_operating_profitability_quality_field"
    payload["parameters"]["operating_profit_quality"] = {
        "operating_income_current_value_required_gt": 0.0,
        "canonical": "operating_income",
        "applies_to": "exp-20260527-017 default-off paper candidate rows before daily top-1 selection",
        "uses_future_data": False,
        "production_visible_field": "PIT SEC Companyfacts latest quarterly operating_income filed <= signal_date",
        "revenue_used_for_diagnostic_margin_only": True,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "skip unless latest quarterly operating_income > 0",
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
            "candidate_pool / entry alpha: positive quarterly operating income is "
            "a stronger free-data source-quality field for the Companyfacts+RS "
            "paper candidate pool than another growth or RS threshold."
        ),
        "2_history_check": {
            "exp-20260527-017": (
                "Single-fact source had aggregate EV +5.2015 and PnL +92488.83 "
                "but failed old_thin drawdown and APP concentration."
            ),
            "exp-20260527-020": (
                "Dual EPS+revenue growth remained high gross EV but failed "
                "drawdown and concentration; this run tests profitability, not "
                "growth-source breadth."
            ),
            "exp-20260527-023/903": (
                "QQQ confirmation and sector-exposure governance failed; this run "
                "does not touch market confirmation or exposure caps."
            ),
            "playbook": (
                "A revisit is eligible only with a materially different "
                "source-quality field outside basic growth+RS governance."
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
            "exp_20260528_004_fundamental_growth_rs_operating_profit_quality.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "PIT operating_income current quarter fact filed <= signal_date",
    ]
    payload["gate2"]["note"] = (
        "SEC operating-income rows are filtered by filed <= signal_date. RS, "
        "trend, liquidity, and returns use signal-date or trailing OHLCV only. "
        "Paper entry occurs at the next open; no LLM, news, hidden event field, "
        "or future bar is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No new core filter or live entry rule was added. The operating-profit "
        "quality condition only changes default-off paper sleeve selection, so "
        "core survival is unchanged."
    )
    payload["operating_profit_quality_audit"] = OPERATING_QUALITY_AUDIT
    payload["fundamental_growth_rs_audit"] = prev.FUNDAMENTAL_RS_AUDIT
    payload["reference_single_fact_exp17_comparison"] = _reference_comparison(payload)
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, and Kova intraday because "
        "recent records show sparse or readiness-blocked attribution. Skipped VCP, "
        "VBB, state-surface, broad-market, and nearby Companyfacts+RS growth, RS, "
        "top-N, fixed-notional, cooldown, extension, QQQ, and sector-exposure "
        "retunes per playbook freeze guidance. This run tests profitability quality."
    )
    payload["interpretation"] = (
        "The operating-profit Companyfacts+RS sleeve cleared Gate 4 as a replay-only "
        "lead. It is still not live capital; promotion requires a shared default-off "
        "paper adapter, daily report exposure, forward replacement-value ledger, "
        "and parity tests."
        if gate4_passed
        else (
            "The operating-profit Companyfacts+RS sleeve did not clear Gate 4. Do not "
            "promote it or retry nearby Companyfacts+RS profitability, growth, RS, "
            "top-N, cooldown, extension, QQQ, or sector-exposure thresholds on the "
            "frozen windows without forward rows or a materially new field."
        )
    )
    payload["next_evidence_needed"] = (
        "If positive, implement only as shared default-off paper before activation; "
        "if rejected, require forward rows or a new source-quality field outside "
        "basic growth, RS, and one-line profitability variants."
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
        "# exp-20260528-004 Fundamental Growth + RS Operating-Profit Quality",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: require latest PIT quarterly operating income to be "
            "positive inside the exp-20260527-017 Companyfacts-growth + OHLCV-RS "
            "default-off paper candidate source."
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
        audit = payload["operating_profit_quality_audit"].get(label, {})
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
            "## Operating-Profit Quality Audit",
            "",
            "```json",
            json.dumps(payload["operating_profit_quality_audit"], indent=2, sort_keys=True),
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
        "title": "Fundamental growth + RS operating-profit quality scout",
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
