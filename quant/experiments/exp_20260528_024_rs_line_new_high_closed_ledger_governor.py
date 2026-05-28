"""exp-20260528-024: RS-line new-high closed-ledger governor.

Alpha search. The raw RS-line new-high default-off paper sleeve from
exp-20260527-013 had positive aggregate EV/PnL and broad sample coverage, but
failed Gate 4 because late_strong regressed and max drawdown drift was too
large. This experiment keeps that free-OHLCV candidate source fixed and tests
one structural production-visible governor: scale paper notional using only
closed sleeve outcomes whose exit_date is before the next paper entry.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict, defaultdict
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

import exp_20260527_013_rs_line_new_high_paper_sleeve as rs_source  # noqa: E402


EXPERIMENT_ID = "exp-20260528-024"
STEM = "rs_line_new_high_closed_ledger_governor"
TRIAL_FAMILY = "relative_strength_line_new_high_closed_ledger_governor"
CHANGED_VARIABLE = "rs_line_new_high_closed_ledger_governor_profile_v1"
RULE_VERSION = "rs_line_new_high_closed_ledger_governor_v1"
SOURCE_RULE_VERSION = rs_source.RULE_VERSION

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

TICKER_CLOSED_PROFIT_CAP_USD = 9_000.0
TICKER_PROFIT_CAP_SCALAR = 0.05
GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD = 7_500.0
GLOBAL_DRAWDOWN_SCALAR = 0.25

RS_LINE_GOVERNOR_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


base = rs_source.base
ohlcv_helper = rs_source.ohlcv_helper


def _configure_modules() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MAX_PAPER_TRADES_PER_DAY = rs_source.MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = rs_source.MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = rs_source.MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = rs_source.MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = rs_source.MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = rs_source.MAX_POSITIVE_HHI
    base.shadow = ohlcv_helper
    base._candidate_rows_for_window = rs_source._candidate_rows_for_window
    base._select_paper_trades = _select_governed_paper_trades
    rs_source.RS_LINE_AUDIT.clear()
    RS_LINE_GOVERNOR_AUDIT.clear()
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(ohlcv_helper, name):
            setattr(ohlcv_helper, name, None)


def _round(value: Any, digits: int = 6) -> Any:
    return base._round(value, digits)


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _money(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _update_closed_state(
    pending_closes: list[dict[str, Any]],
    entry_date: str,
    cumulative_closed_pnl: float,
    peak_closed_pnl: float,
    ticker_closed_pnl: defaultdict[str, float],
) -> tuple[list[dict[str, Any]], float, float, float]:
    still_pending: list[dict[str, Any]] = []
    for trade in sorted(pending_closes, key=lambda row: _date10(row.get("exit_date"))):
        exit_date = _date10(trade.get("exit_date"))
        if exit_date and exit_date < entry_date:
            pnl = _money(trade.get("pnl"))
            cumulative_closed_pnl += pnl
            peak_closed_pnl = max(peak_closed_pnl, cumulative_closed_pnl)
            ticker = str(trade.get("ticker") or "").upper()
            if ticker:
                ticker_closed_pnl[ticker] += pnl
        else:
            still_pending.append(trade)
    closed_drawdown = peak_closed_pnl - cumulative_closed_pnl
    return still_pending, cumulative_closed_pnl, peak_closed_pnl, closed_drawdown


def _scale_trade(trade: dict[str, Any], notional_scalar: float) -> dict[str, Any]:
    original_notional = _money(trade.get("paper_notional_usd")) or base.BASE_NOTIONAL_USD
    original_pnl = _money(trade.get("pnl"))
    return {
        **trade,
        "source_rule_version": SOURCE_RULE_VERSION,
        "closed_ledger_governor_rule_version": RULE_VERSION,
        "closed_ledger_governor_trade_enabled": False,
        "closed_ledger_governor_alters_orders": False,
        "closed_ledger_governor_known_at": "closed paper ledger rows with exit_date < entry_date",
        "paper_notional_usd_before_governor": _round(original_notional, 2),
        "pnl_before_governor": _round(original_pnl, 2),
        "paper_notional_usd": _round(original_notional * notional_scalar, 2),
        "pnl": _round(original_pnl * notional_scalar, 2),
        "closed_ledger_notional_scalar": _round(notional_scalar, 6),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _select_governed_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    pending_closes: list[dict[str, Any]] = []
    ticker_closed_pnl: defaultdict[str, float] = defaultdict(float)
    cumulative_closed_pnl = 0.0
    peak_closed_pnl = 0.0
    max_closed_drawdown_seen = 0.0
    audit: Counter[str] = Counter()
    ticker_scaled_counts: Counter[str] = Counter()
    global_scaled_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)

    for row in candidates:
        date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        if row.get("same_ticker_ab_overlap"):
            audit["same_ticker_core_overlap_filtered"] += 1
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= rs_source.MAX_PAPER_TRADES_PER_DAY:
            audit["daily_top1_filtered"] += 1
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            audit["missing_trade_filtered"] += 1
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue

        entry_date = _date10(trade.get("entry_date") or date)
        pending_closes, cumulative_closed_pnl, peak_closed_pnl, closed_drawdown = (
            _update_closed_state(
                pending_closes,
                entry_date,
                cumulative_closed_pnl,
                peak_closed_pnl,
                ticker_closed_pnl,
            )
        )
        max_closed_drawdown_seen = max(max_closed_drawdown_seen, closed_drawdown)

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
        governed_trade = _scale_trade(trade, notional_scalar)
        governed_trade.update(
            {
                "ticker_closed_profit_cap_usd": TICKER_CLOSED_PROFIT_CAP_USD,
                "ticker_closed_pnl_before_entry": _round(ticker_closed_pnl[ticker], 2),
                "ticker_profit_cap_scalar": ticker_profit_scalar,
                "global_closed_drawdown_trigger_usd": GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD,
                "global_closed_pnl_before_entry": _round(cumulative_closed_pnl, 2),
                "global_closed_peak_pnl_before_entry": _round(peak_closed_pnl, 2),
                "global_closed_drawdown_before_entry": _round(closed_drawdown, 2),
                "global_drawdown_scalar": global_drawdown_scalar,
            }
        )
        if ticker_profit_scalar < 1.0:
            audit["ticker_profit_cap_scaled"] += 1
            ticker_scaled_counts[ticker] += 1
        if global_drawdown_scalar < 1.0:
            audit["global_drawdown_scaled"] += 1
            global_scaled_counts[ticker] += 1
        if notional_scalar < 1.0:
            pnl_delta_by_ticker[ticker] += _money(governed_trade.get("pnl")) - _money(trade.get("pnl"))

        selected.append(governed_trade)
        pending_closes.append(governed_trade)
        used_date_counts[date] += 1

    label = _window_label_for_candidates(candidates)
    RS_LINE_GOVERNOR_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "selected_trade_count": len(selected),
        "raw_candidate_count": len(candidates),
        "selected_ticker_count": len({str(row.get("ticker") or "").upper() for row in selected}),
        "max_closed_drawdown_seen": _round(max_closed_drawdown_seen, 2),
        "ending_closed_pnl": _round(cumulative_closed_pnl, 2),
        "ending_peak_closed_pnl": _round(peak_closed_pnl, 2),
        "ticker_scaled_counts": dict(sorted(ticker_scaled_counts.items())),
        "global_scaled_counts": dict(sorted(global_scaled_counts.items())),
        "governor_pnl_delta_by_ticker": {
            ticker: _round(delta, 2) for ticker, delta in sorted(pnl_delta_by_ticker.items())
        },
        **dict(sorted(audit.items())),
    }
    return selected, filtered


def _window_label_for_candidates(candidates: list[dict[str, Any]]) -> str:
    dates = [str(row.get("date") or "") for row in candidates if row.get("date")]
    if not dates:
        return "unknown"
    min_date = min(dates)
    max_date = max(dates)
    for label, cfg in base.WINDOWS.items():
        if str(cfg["start"]) <= min_date and max_date <= str(cfg["end"]):
            return label
    return f"{min_date}_{max_date}"


def _source_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    source_path = REPO_ROOT / "experiments" / "logs" / "exp-20260527-013.json"
    if not source_path.exists():
        return {"available": False, "reason": "missing_exp_20260527_013_reference"}
    source = json.loads(source_path.read_text(encoding="utf-8"))
    before = source.get("after_metrics") or {}
    after = payload.get("after_metrics") or {}
    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label in base.WINDOWS:
        src = before.get(label) or {}
        cur = after.get(label) or {}
        by_window[label] = {
            "expected_value_score_delta": _round(
                _money(cur.get("expected_value_score")) - _money(src.get("expected_value_score")),
                6,
            ),
            "total_pnl_delta": _round(
                _money(cur.get("total_pnl")) - _money(src.get("total_pnl")),
                2,
            ),
            "max_drawdown_pct_delta": _round(
                _money(cur.get("max_drawdown_pct")) - _money(src.get("max_drawdown_pct")),
                6,
            ),
        }
    src_agg = source.get("delta_metrics", {}).get("aggregate", {})
    cur_agg = payload.get("delta_metrics", {}).get("aggregate", {})
    return {
        "available": True,
        "reference_experiment_id": "exp-20260527-013",
        "reference_decision": source.get("decision"),
        "by_window_delta_after_vs_raw_rs_line": by_window,
        "aggregate_delta_after_vs_raw_rs_line": {
            "expected_value_score_delta_sum": _round(
                _money(cur_agg.get("after_expected_value_score_sum"))
                - _money(src_agg.get("after_expected_value_score_sum")),
                6,
            ),
            "total_pnl_delta_sum": _round(
                _money(cur_agg.get("after_total_pnl_sum"))
                - _money(src_agg.get("after_total_pnl_sum")),
                2,
            ),
            "max_drawdown_pct_delta_max": _round(
                _money(cur_agg.get("max_drawdown_delta_max"))
                - _money(src_agg.get("max_drawdown_delta_max")),
                6,
            ),
        },
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_rs_line_new_high_closed_ledger_governor"
        if gate4_passed
        else "rejected_rs_line_new_high_closed_ledger_governor"
    )
    source_comparison = _source_comparison(payload)
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "The raw RS-line new-high paper sleeve has a broad free-OHLCV gross edge "
        "but failed on drawdown and one regressed window. A closed-ledger governor "
        "using only prior closed paper outcomes may retain candidate-pool edge "
        "while reducing repeated-winner concentration and post-loss drawdown."
    )
    payload["change_type"] = "relative_strength_line_new_high_closed_ledger_governor"
    payload["mechanism_family"] = "free_ohlcv_relative_strength_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 1
    payload["nearby_prior_experiments"] = [
        "exp-20260527-013",
        "exp-20260527-022",
        "exp-20260527-011",
        "exp-20260528-008",
        "exp-20260528-015",
        "exp-20260528-016",
        "exp-20260528-017",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = (
        "production_visible_closed_paper_ledger_governor_on_existing_free_ohlcv_candidate_pool"
    )
    payload["parameters"]["closed_ledger_governor"] = {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "ticker_closed_profit_cap_usd": TICKER_CLOSED_PROFIT_CAP_USD,
        "ticker_profit_cap_scalar": TICKER_PROFIT_CAP_SCALAR,
        "global_closed_drawdown_trigger_usd": GLOBAL_CLOSED_DRAWDOWN_TRIGGER_USD,
        "global_drawdown_scalar": GLOBAL_DRAWDOWN_SCALAR,
        "closed_rows_allowed": "exit_date < entry_date only",
        "trade_enabled": False,
        "alters_orders": False,
    }
    payload["parameters"]["locked_variables"] = [
        "all exp-20260527-013 RS-line candidate filters",
        "all exp-20260527-013 RS-line ranking keys",
        "daily top-1 paper selection",
        "same-ticker core overlap skip",
        "paper notional base before governor",
        "10-trading-day paper hold",
        "core universe membership",
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
            "candidate_pool / risk allocation: RS-line new highs are a candidate "
            "pool expansion lead, and the only new variable is a closed-ledger "
            "paper governor to control drawdown/concentration."
        ),
        "2_history_check": {
            "exp-20260527-013": (
                "Raw RS-line new-high paper sleeve improved aggregate EV +0.8728 "
                "and PnL +$20,586.96 but failed Gate 4 due late_strong regression "
                "and max drawdown drift +11.65pp."
            ),
            "exp-20260528-008": (
                "A structurally similar closed-ledger governor rescued the "
                "Companyfacts operating-profit gross edge by reducing drawdown "
                "and concentration."
            ),
            "difference": (
                "This does not retune RS-line lookback, near-high, return, "
                "liquidity, top-N, hold-day, or notional thresholds."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no PnL-regressed window; >=30 paper trades "
            "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
            "concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260528_024_rs_line_new_high_closed_ledger_governor.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for relative-strength-line ratio",
        "selected RS-line paper trade entry_date/exit_date/pnl",
        "closed paper ledger rows with exit_date < entry_date",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The new governor uses no future open trade outcomes. It reads only "
        "paper trades already closed before the candidate's next-open entry."
    )
    payload["gate3"]["candidate_pool_changed"] = False
    payload["gate3"]["note"] = (
        "No new core filter, live entry rule, or paper candidate filter was "
        "added. The source candidate pool is fixed from exp-20260527-013 and "
        "only selected-trade notional is governed."
    )
    payload["rs_line_new_high_audit"] = rs_source.RS_LINE_AUDIT
    payload["closed_ledger_governor_audit"] = RS_LINE_GOVERNOR_AUDIT
    payload["source_exp_20260527_013_comparison"] = source_comparison
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, Kova, VCP/VBB retunes, "
        "Companyfacts retunes, RS-line threshold/lookback/top-N/hold retunes, "
        "and live activation. The experiment tests only the closed-ledger "
        "governor profile on an already measured free-OHLCV candidate-pool lead."
    )
    payload["interpretation"] = (
        "Accepted: the closed-ledger governor makes the RS-line new-high paper "
        "candidate pool pass Gate 4 as a default-off paper lead. It still requires "
        "a shared adapter/parity step before any production-visible retention."
        if gate4_passed
        else (
            "Rejected: the closed-ledger governor did not make RS-line new highs "
            "robust enough across all three windows. Do not retry nearby RS-line "
            "governor thresholds or source thresholds on the frozen sample without "
            "forward rows or a materially orthogonal production-visible field."
        )
    )
    payload["next_evidence_needed"] = (
        "Forward RS-line paper rows or a materially orthogonal source-quality "
        "field; avoid nearby RS-line lookback, near-high, top-N, hold, notional, "
        "or closed-ledger threshold retunes on the same frozen windows."
    )
    payload["production_impact"].update(
        {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result would require a shared default-off RS-line "
                "paper adapter, daily report exposure, forward replacement-value "
                "ledger, and parity tests before any live/default behavior changes."
            ),
        }
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        "quant/experiments/exp_20260527_013_rs_line_new_high_paper_sleeve.py",
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(DOC_TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    if not gate4_passed and not payload.get("rejection_reason"):
        payload["rejection_reason"] = "; ".join(
            payload.get("gate4", {}).get("failed_reasons") or ["gate4_failed"]
        )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Gov scaled |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["closed_ledger_governor_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {scaled} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                scaled=(
                    int(audit.get("ticker_profit_cap_scaled") or 0)
                    + int(audit.get("global_drawdown_scaled") or 0)
                ),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} RS-Line New-High Closed-Ledger Governor",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: keep the exp-20260527-013 RS-line new-high "
                "candidate pool fixed and apply a closed-ledger paper governor "
                "using only prior closed sleeve outcomes."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs core: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Raw RS-Line Comparison",
            "",
            "```json",
            json.dumps(payload["source_exp_20260527_013_comparison"], indent=2, sort_keys=True),
            "```",
            "",
            "## Governor Audit",
            "",
            "```json",
            json.dumps(payload["closed_ledger_governor_audit"], indent=2, sort_keys=True),
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
                "Replay-only default-off paper. No shared policy, run adapter, "
                "backtester adapter, production watchlist, live/default order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "RS-line closed-ledger governor",
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": "alpha_search",
        "updated_at": payload["timestamp"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
        "owner": "alpha-search",
    }
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, ticket)
    base._write_json(DOC_TICKET_JSON, ticket)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _update_payload(base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "source_comparison": payload["source_exp_20260527_013_comparison"],
                    "closed_ledger_governor_audit": payload["closed_ledger_governor_audit"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
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
