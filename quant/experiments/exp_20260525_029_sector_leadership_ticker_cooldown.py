"""exp-20260525-029: sector-leadership ticker-cooldown paper sleeve.

This alpha search follows the rejected exp-20260525-916 sector-leadership
paper source. The raw source had strong aggregate EV but failed on
late_strong regression, old_thin drawdown drift, and single-name
concentration. The single tested variable here is a source-level same-ticker
cooldown equal to the 10-trading-day paper holding period.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
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

import exp_20260525_916_sector_leadership_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260525-029"
STEM = "sector_leadership_ticker_cooldown"
TRIAL_FAMILY = "sector_leadership_ticker_crowding_cooldown_paper_sleeve"
CHANGED_VARIABLE = "sector_leadership_same_ticker_10d_cooldown_v1"

COOLDOWN_TRADING_DAYS = base.HOLD_DAYS
MIN_TARGET_TRADES = 60
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.35
MAX_POSITIVE_HHI = 0.25

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG


def _trading_date_index(snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        date: idx
        for idx, date in enumerate(base.shadow._trading_dates(snapshot))
    }


def _select_paper_trades_with_cooldown(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    last_selected_idx_by_ticker: dict[str, int] = {}
    date_idx = _trading_date_index(snapshot)

    for row in candidates:
        date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        current_idx = date_idx.get(date)
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if current_idx is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_index"})
            continue
        last_idx = last_selected_idx_by_ticker.get(ticker)
        if last_idx is not None and current_idx - last_idx <= COOLDOWN_TRADING_DAYS:
            filtered.append(
                {
                    **row,
                    "filter_reason": "same_ticker_source_cooldown",
                    "cooldown_trading_days": COOLDOWN_TRADING_DAYS,
                    "previous_selected_signal_days_ago": current_idx - last_idx,
                }
            )
            continue
        if used_date_counts[date] >= base.MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        trade["source_cooldown_trading_days"] = COOLDOWN_TRADING_DAYS
        selected.append(trade)
        used_date_counts[date] += 1
        last_selected_idx_by_ticker[ticker] = current_idx

    return selected, filtered


def _failed_gate_checks(payload: dict[str, Any]) -> list[str]:
    gate4 = payload.get("gate4") or {}
    failed: list[str] = []
    if not gate4.get("aggregate_ev_delta_positive"):
        failed.append("aggregate_ev_not_positive")
    if not gate4.get("aggregate_pnl_delta_positive"):
        failed.append("aggregate_pnl_not_positive")
    if gate4.get("windows_ev_improved") != len(base.WINDOWS) or gate4.get("windows_ev_regressed"):
        failed.append("window_ev_regression")
    if gate4.get("windows_pnl_regressed"):
        failed.append("window_pnl_regression")
    if gate4.get("target_trade_count", 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(gate4.get("target_windows") or []) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if gate4.get("max_drawdown_worse", 0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not (gate4.get("target_concentration") or {}).get("passed"):
        failed.append("target_concentration_failed")
    return failed


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    passed = bool((payload.get("gate4") or {}).get("passed"))
    decision = (
        "promising_replay_only_sector_leadership_ticker_cooldown"
        if passed
        else "rejected_sector_leadership_ticker_cooldown"
    )
    aggregate = payload["delta_metrics"]["aggregate"]

    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "The sector-leadership paper source may have real candidate-pool alpha, "
        "but raw daily top-1 selection over-concentrates in the same ticker during "
        "its own 10-trading-day paper holding window. A same-ticker source "
        "cooldown should improve replacement quality and tail behavior without "
        "changing sector-rank or return thresholds."
    )
    payload["change_type"] = "sector_leadership_crowding_governed_paper_sleeve"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["nearby_prior_experiments"] = [
        "exp-20260525-916",
        "exp-20260426-049",
        "exp-20260525-028",
    ]
    payload["multiple_testing_risk_bucket"] = "moderate"
    payload["new_evidence_type"] = (
        "production_visible_source_crowding_field_derived_from_rejected_raw_"
        "sector_leadership_tail_failure"
    )
    payload["parameters"]["source_crowding_governance"] = {
        "same_ticker_cooldown_trading_days": COOLDOWN_TRADING_DAYS,
        "cooldown_anchor": "prior selected sector-leadership paper signal date",
        "rationale": (
            "equal to the fixed paper hold; prevents overlapping paper exposure "
            "to the same name from the same source"
        ),
        "known_at": "paper source state at signal-date close before next-open paper entry",
    }
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        }
    )
    payload["parameters"]["locked_variables"].append(
        "sector-leadership rank and return thresholds from exp-20260525-916"
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry / candidate_pool / risk allocation: same-source ticker "
            "crowding, not sector-leadership itself, caused the raw source's "
            "tail failure. A 10-trading-day same-ticker cooldown is a "
            "production-visible paper-state field."
        ),
        "2_history_check": {
            "exp-20260525-916": (
                "Raw sector-leadership top-1 source improved aggregate EV by "
                "+4.0485 and PnL by $63,829.18, but failed Gate 4 on late_strong "
                "regression, old_thin drawdown drift, and concentration."
            ),
            "exp-20260525-028": (
                "Opening-range sector-leadership confirmation was rejected; this "
                "does not touch opening-range and does not retune sector ranks."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
            "3/3 EV-improved windows; no EV/PnL-regressed window; >=60 paper "
            "trades across all 3 windows; drawdown drift <=0.5pp; survival "
            ">=5%; concentration inside stricter guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260525_029_sector_leadership_ticker_cooldown.py"
        ),
    }
    payload["gate2"]["runtime_fields"].extend(
        [
            "source-level prior selected ticker state",
            "SPY trading-date index for cooldown distance",
        ]
    )
    payload["gate4"]["failed_checks"] = [] if passed else _failed_gate_checks(payload)
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-residual because current "
        "coverage/readiness remains sparse. Skipped volatility-contraction, "
        "opening-range, Space, AI/compute, SEC, and broad-market retreads due "
        "fresh anti-repeat gates. This follows the strongest raw candidate-pool "
        "lead from exp-20260525-916 but changes only source-level same-ticker "
        "crowding governance, not sector thresholds."
    )
    payload["interpretation"] = (
        "The sector-leadership same-ticker cooldown cleared replay-only Gate 4. "
        "No shared production adapter was promoted; a production-visible "
        "default-off paper adapter plus parity tests would be required before "
        "forward tracking."
        if passed
        else (
            "The sector-leadership same-ticker cooldown did not clear Gate 4. "
            "Do not retry nearby sector-leadership cooldown/crowding variants "
            "on the same frozen sample without forward rows or a distinct "
            "non-price source confirmation."
        )
    )
    payload["rejection_reason"] = None if passed else "; ".join(payload["gate4"]["failed_checks"])
    payload["next_evidence_needed"] = (
        "If retained, build a shared default-off paper adapter that exposes the "
        "same ticker-cooldown state in run.py and records forward replacement "
        "value before activation review."
        if passed
        else (
            "Forward sector-leadership paper rows or a distinct non-price/event "
            "confirmation; do not retune sector-rank, return, or cooldown "
            "thresholds on the frozen sample."
        )
    )
    payload["production_impact"]["promotion_requirement"] = (
        "Promotion would require moving this exact same-ticker paper-state "
        "cooldown into a shared default-off adapter and exposing the same "
        "metadata through run.py with parity tests."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector-Leadership Ticker-Cooldown",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: keep the exp-20260525-916 sector-leadership "
                "source fixed, but skip same-ticker candidates selected by this "
                "source during the prior 10 trading days."
            ),
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- changed_variable: `{payload['changed_variable']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
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
        ]
    ) + "\n"


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Replay-only default-off sector-leadership paper source with a "
            "10-trading-day same-ticker source cooldown."
        ),
        "change_type": payload["change_type"],
        "mechanism_family": "sector_leadership_free_ohlcv_candidate_pool",
        "trial_family": payload["trial_family"],
        "trial_variant_id": "same_ticker_10d_cooldown",
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": base._repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "date_range": payload["backtest_protocol"]["windows"],
        "gate_questions": payload["gate_questions"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "target_trade_summary": payload["target_trade_summary"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Sector-leadership ticker-cooldown paper sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._append_jsonl_once(EXPERIMENT_LOG, _experiment_log_entry(payload))


def main() -> int:
    _configure_base_module()
    base._select_paper_trades = _select_paper_trades_with_cooldown
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
                    "target_trade_summary": payload["target_trade_summary"],
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
