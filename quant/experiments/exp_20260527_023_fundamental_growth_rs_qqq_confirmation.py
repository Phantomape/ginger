"""exp-20260527-023: fundamental growth + RS QQQ confirmation scout.

Alpha search. This retests the exp-20260527-017 free-data candidate source with
one orthogonal market-participation variable: default-off paper candidates are
eligible only when QQQ's 20-trading-day close-to-close return is greater than
SPY's 20-trading-day close-to-close return on the signal date.

Core entries, ranking, sizing, exits, LLM/news paths, watchlists, and orders are
unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260527_017_fundamental_growth_rs_candidate_pool as prev


EXPERIMENT_ID = "exp-20260527-023"
STEM = "fundamental_growth_rs_qqq_confirmation"
TRIAL_FAMILY = "fundamental_growth_rs_default_off_candidate_pool"
CHANGED_VARIABLE = "fundamental_growth_rs_qqq20_gt_spy20_confirmation_v1"
RULE_VERSION = "fundamental_growth_rs_qqq_confirmation_v1"
MARKET_CONFIRMATION_LOOKBACK_DAYS = 20

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REFERENCE_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260527-017.json"

CONFIRMATION_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    prev._configure_base_module()
    prev.base._candidate_rows_for_window = _candidate_rows_for_window


def _window_label(cfg: dict[str, str]) -> str:
    for label, window_cfg in prev.base.WINDOWS.items():
        if window_cfg is cfg:
            return label
    return str(cfg.get("start") or "unknown")


def _market_confirmation_by_date(
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    spy_rows = prev.ohlcv_helper._series(snapshot, "SPY")
    qqq_rows = prev.ohlcv_helper._series(snapshot, "QQQ")
    spy_index = prev.ohlcv_helper._row_index(spy_rows)
    qqq_index = prev.ohlcv_helper._row_index(qqq_rows)
    out: dict[str, dict[str, Any]] = {}
    for date, spy_idx in spy_index.items():
        qqq_idx = qqq_index.get(date)
        if qqq_idx is None:
            continue
        spy_ret = prev._close_return(
            spy_rows, spy_idx - MARKET_CONFIRMATION_LOOKBACK_DAYS, spy_idx
        )
        qqq_ret = prev._close_return(
            qqq_rows, qqq_idx - MARKET_CONFIRMATION_LOOKBACK_DAYS, qqq_idx
        )
        if spy_ret is None or qqq_ret is None:
            out[date] = {
                "market_confirmation_status": "missing_lookback",
                "qqq20_gt_spy20_confirmation": False,
            }
            continue
        out[date] = {
            "market_confirmation_status": "ok",
            "market_confirmation_lookback_days": MARKET_CONFIRMATION_LOOKBACK_DAYS,
            "qqq_20d_return": prev.base._round(qqq_ret, 6),
            "spy_20d_return": prev.base._round(spy_ret, 6),
            "qqq_minus_spy_20d_return": prev.base._round(qqq_ret - spy_ret, 6),
            "qqq20_gt_spy20_confirmation": qqq_ret > spy_ret,
            "market_confirmation_known_at": (
                "after_signal_date_close_before_next_open_paper_entry"
            ),
        }
    return out


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = prev._candidate_rows_for_window(snapshot, cfg, universe, before_result)
    confirmation_by_date = _market_confirmation_by_date(snapshot)
    retained: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        date = str(row.get("date") or "")
        confirmation = confirmation_by_date.get(date) or {
            "market_confirmation_status": "missing_market_date",
            "qqq20_gt_spy20_confirmation": False,
        }
        enriched = {
            **row,
            **confirmation,
            "market_confirmation_rule_version": RULE_VERSION,
        }
        if confirmation.get("qqq20_gt_spy20_confirmation"):
            retained.append(
                {
                    **enriched,
                    "selection_rule_version": RULE_VERSION,
                    "rule_version": RULE_VERSION,
                }
            )
            continue
        filtered.append(
            {
                **enriched,
                "filter_reason": "qqq20_not_greater_than_spy20",
            }
        )

    label = _window_label(cfg)
    prev.FUNDAMENTAL_RS_AUDIT[label]["qqq_confirmed_candidates"] = len(retained)
    prev.FUNDAMENTAL_RS_AUDIT[label]["qqq_confirmed_days"] = len(
        {row["date"] for row in retained}
    )
    prev.FUNDAMENTAL_RS_AUDIT[label]["qqq_confirmed_tickers"] = len(
        {row["ticker"] for row in retained}
    )
    CONFIRMATION_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "market_confirmation_lookback_days": MARKET_CONFIRMATION_LOOKBACK_DAYS,
        "input_candidates": len(rows),
        "retained_candidates": len(retained),
        "filtered_candidates": len(filtered),
        "retained_days": len({row["date"] for row in retained}),
        "filtered_days": len({row["date"] for row in filtered}),
        "retained_unique_tickers": len({row["ticker"] for row in retained}),
        "filtered_unique_tickers": len({row["ticker"] for row in filtered}),
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
        "by_window_delta_after_vs_unconfirmed_source": by_window,
        "aggregate_delta_after_vs_unconfirmed_source": {
            "expected_value_score_delta_sum": prev.base._round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": prev.base._round(
                cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"], 2
            ),
            "max_drawdown_pct_delta_max": prev.base._round(
                cur_agg["max_drawdown_pct_max"] - ref_agg["max_drawdown_pct_max"], 6
            ),
        },
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_fundamental_growth_rs_qqq_confirmation"
        if gate4_passed
        else "rejected_fundamental_growth_rs_qqq_confirmation"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / entry: the exp-20260527-017 PIT SEC Companyfacts growth "
        "plus OHLCV RS source has strong gross alpha but failed old-window drawdown "
        "and ticker concentration. Requiring QQQ 20d return to exceed SPY 20d "
        "return should keep the source active only when growth-led risk appetite is "
        "broad enough, without retuning growth thresholds, RS thresholds, top-N, "
        "notional, cooldown, extension, hold period, or exits."
    )
    payload["change_type"] = "fundamental_growth_rs_market_confirmation_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 8
    payload["nearby_prior_experiments"] = [
        "exp-20260525-022",
        "exp-20260527-013",
        "exp-20260527-017",
        "exp-20260527-018",
        "exp-20260527-019",
        "exp-20260527-020",
        "exp-20260527-022",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "production_visible_free_ohlcv_market_confirmation_field"
    payload["parameters"]["market_confirmation"] = {
        "benchmark_pair": "QQQ_vs_SPY",
        "lookback_trading_days": MARKET_CONFIRMATION_LOOKBACK_DAYS,
        "rule": "QQQ close-to-close 20d return > SPY close-to-close 20d return",
        "known_at": "after signal-date close, before next-open paper entry",
        "uses_future_data": False,
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "skip if QQQ 20d return <= SPY 20d return",
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
        "dual EPS+revenue growth requirement disabled",
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
            "candidate_pool / entry alpha: the Companyfacts-growth + OHLCV-RS "
            "candidate source should have better risk-adjusted replacement value "
            "when Nasdaq/growth participation is beating broad-market SPY."
        ),
        "2_history_check": {
            "exp-20260527-017": (
                "Unconfirmed source had aggregate EV +5.2015 and PnL +92488.83, "
                "but failed old_thin drawdown (+12.64pp) and concentration."
            ),
            "exp-20260527-018": (
                "20-trading-day ticker cooldown fixed concentration but regressed "
                "late_strong and still failed drawdown."
            ),
            "exp-20260527-019": (
                "50d extension guard fixed concentration but regressed late_strong "
                "and still failed drawdown."
            ),
            "exp-20260527-020": (
                "Dual EPS+revenue confirmation improved all windows but stayed "
                "too concentrated and drawdown-heavy."
            ),
            "exp-20260525-022": (
                "QQQ 20d > SPY 20d was the accepted orthogonal market-confirmation "
                "field for VCP; this run tests the same free-data concept on a "
                "different candidate-pool source, not a VCP retune."
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
            "exp_20260527_023_fundamental_growth_rs_qqq_confirmation.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy and market confirmation",
        "QQQ OHLCV Close rows for market confirmation",
    ]
    payload["gate2"]["note"] = (
        "SEC growth rows are filtered by filed <= signal_date. RS, trend, liquidity, "
        "and returns use signal-date or trailing OHLCV only. QQQ/SPY confirmation "
        "uses signal-date close-to-close trailing returns and paper entry occurs at "
        "the next open."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No new core filter or live entry rule was added. The confirmation only "
        "changes default-off paper sleeve selection, so core survival is unchanged."
    )
    payload["qqq_confirmation_audit"] = CONFIRMATION_AUDIT
    payload["fundamental_growth_rs_audit"] = prev.FUNDAMENTAL_RS_AUDIT
    payload["reference_unconfirmed_exp17_comparison"] = _reference_comparison(payload)
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, and Kova intraday because "
        "recent records show sparse or readiness-blocked attribution. Skipped VCP, "
        "VBB, state-surface, sector-leadership, and broad-market threshold/top-N/"
        "profile retunes per playbook freeze guidance. This run uses a free, "
        "production-visible market-confirmation field on the strongest recent "
        "candidate-pool gross edge."
    )
    payload["interpretation"] = (
        "The QQQ-confirmed Companyfacts+RS sleeve cleared Gate 4 as a replay-only "
        "lead. It is still not live capital; promotion requires a shared default-off "
        "paper adapter, daily report exposure, forward replacement-value ledger, "
        "and parity tests."
        if gate4_passed
        else (
            "The QQQ-confirmed Companyfacts+RS sleeve did not clear Gate 4. Do not "
            "promote it or retry nearby Companyfacts+RS QQQ/SPY, growth, RS, top-N, "
            "cooldown, or extension thresholds on the frozen windows without forward "
            "rows or a materially new source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If positive, implement only as shared default-off paper before activation; "
        "if rejected, require forward rows or a new source-quality field, not a "
        "nearby QQQ/SPY or Companyfacts/RS threshold retune."
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
        "# exp-20260527-023 Fundamental Growth + RS QQQ Confirmation",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: require QQQ 20-trading-day close-to-close return to "
            "be greater than SPY 20-trading-day close-to-close return before the "
            "exp-20260527-017 Companyfacts-growth + OHLCV-RS default-off paper "
            "candidate source can select a trade."
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
        audit = payload["qqq_confirmation_audit"].get(label, {})
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
            "## QQQ Confirmation Audit",
            "",
            "```json",
            json.dumps(payload["qqq_confirmation_audit"], indent=2, sort_keys=True),
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
        "title": "Fundamental growth + RS QQQ confirmation scout",
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
