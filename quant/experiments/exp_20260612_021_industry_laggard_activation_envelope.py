"""Activation-envelope review for industry-relative laggard repair.

This runner does not change signal logic, production code, or paper sleeve
state. It combines the accepted Gate 1-4 evidence from exp-20260607-008 with
post-acceptance OOS replay and genuine production-forward rows from
exp-20260612-019, then decides whether live activation is mature enough.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from industry_relative_laggard_repair_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
)


EXPERIMENT_ID = "exp-20260612-021"
SLEEVE_KEY = "industry_relative_laggard_repair"
SOURCE_EXPERIMENT_ID = "exp-20260607-008"
READINESS_EXPERIMENT_ID = "exp-20260612-019"

SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260607_008_industry_relative_laggard_repair_shared_adapter.json"
)
READINESS_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / READINESS_EXPERIMENT_ID
    / "exp_20260612_019_post_acceptance_oos_replay_readiness.json"
)
STATE_PATH = (
    ROOT / "data" / "paper_sleeves" / SLEEVE_KEY / "state.json"
)
OPEN_POSITIONS_PATH = ROOT / "operator_inputs" / "open_positions.json"
OUTPUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUTPUT_ARTIFACT = (
    OUTPUT_DIR / "exp_20260612_021_industry_laggard_activation_envelope.json"
)
BEFORE_AGGREGATE = OUTPUT_DIR / "before_accepted_stack_aggregate.json"
AFTER_AGGREGATE = OUTPUT_DIR / "after_industry_laggard_shared_helper_aggregate.json"

WINDOW_LABELS = ["late_strong", "mid_weak", "old_thin"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def weighted_average(rows: list[dict[str, Any]], key: str, weight_key: str) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        value = row.get(key)
        weight = row.get(weight_key)
        if isinstance(value, (int, float)) and isinstance(weight, (int, float)):
            numerator += float(value) * float(weight)
            denominator += float(weight)
    if denominator == 0.0:
        return None
    return round(numerator / denominator, 6)


def aggregate_window_metrics(
    by_window: dict[str, dict[str, Any]],
    *,
    experiment_id: str,
    source_file: str,
) -> dict[str, Any]:
    rows = [by_window[label] for label in WINDOW_LABELS]
    total_signals_generated = sum(int(row.get("signals_generated", 0)) for row in rows)
    total_signals_survived = sum(int(row.get("signals_survived", 0)) for row in rows)
    total_trades = sum(int(row.get("trade_count", 0)) for row in rows)
    strategy_total_return_pct = round(
        sum(float(row.get("strategy_total_return_pct", 0.0)) for row in rows), 6
    )
    return {
        "experiment_id": experiment_id,
        "source_file": source_file,
        "expected_value_score": round(
            sum(float(row.get("expected_value_score", 0.0)) for row in rows), 6
        ),
        "total_pnl": round(sum(float(row.get("total_pnl", 0.0)) for row in rows), 2),
        "max_drawdown_pct": round(
            max(float(row.get("max_drawdown_pct", 0.0)) for row in rows), 6
        ),
        "win_rate": weighted_average(rows, "win_rate", "trade_count"),
        "survival_rate": (
            round(total_signals_survived / total_signals_generated, 6)
            if total_signals_generated
            else None
        ),
        "signals_generated": total_signals_generated,
        "signals_survived": total_signals_survived,
        "total_trades": total_trades,
        "sharpe_daily": weighted_average(rows, "sharpe_daily", "trade_count"),
        "benchmarks": {
            "strategy_total_return_pct": strategy_total_return_pct,
        },
        "window_metrics": {label: by_window[label] for label in WINDOW_LABELS},
    }


def load_open_position_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = load_json(path)
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        for key in ("positions", "open_positions"):
            rows = raw.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def gate2_runtime_field_check() -> dict[str, Any]:
    rows = load_open_position_rows(OPEN_POSITIONS_PATH)
    missing_entry_date = [
        row.get("ticker") for row in rows if not row.get("entry_date")
    ]
    missing_target_price = [
        row.get("ticker") for row in rows if row.get("target_price") in (None, "")
    ]
    return {
        "path": str(OPEN_POSITIONS_PATH.relative_to(ROOT)),
        "position_count": len(rows),
        "entry_date_present": not missing_entry_date,
        "target_price_present": not missing_target_price,
        "missing_entry_date_tickers": missing_entry_date,
        "missing_target_price_tickers": missing_target_price,
        "passed": bool(rows) and not missing_entry_date and not missing_target_price,
    }


def positive_concentration(trades: list[dict[str, Any]]) -> dict[str, Any]:
    positive_by_ticker: dict[str, float] = defaultdict(float)
    for trade in trades:
        ticker = trade.get("ticker")
        pnl = trade.get("pnl")
        if not ticker or not isinstance(pnl, (int, float)) or pnl <= 0:
            continue
        positive_by_ticker[str(ticker)] += float(pnl)
    total = sum(positive_by_ticker.values())
    if total <= 0:
        return {
            "positive_pnl_total": 0.0,
            "max_single_ticker_positive_share": None,
            "positive_pnl_hhi": None,
            "positive_ticker_count": 0,
        }
    shares = [value / total for value in positive_by_ticker.values()]
    return {
        "positive_pnl_total": round(total, 2),
        "max_single_ticker_positive_share": round(max(shares), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares), 6),
        "positive_ticker_count": len(positive_by_ticker),
    }


def find_readiness_row(readiness_report: list[dict[str, Any]]) -> dict[str, Any]:
    for row in readiness_report:
        if row.get("sleeve_key") == SLEEVE_KEY:
            return row
    return {}


def main() -> int:
    source = load_json(SOURCE_ARTIFACT)
    readiness = load_json(READINESS_ARTIFACT)
    state = load_json(STATE_PATH) if STATE_PATH.exists() else {}

    before_aggregate = aggregate_window_metrics(
        source["before_metrics"],
        experiment_id=EXPERIMENT_ID,
        source_file=str(SOURCE_ARTIFACT.relative_to(ROOT)),
    )
    after_aggregate = aggregate_window_metrics(
        source["after_metrics"],
        experiment_id=EXPERIMENT_ID,
        source_file=str(SOURCE_ARTIFACT.relative_to(ROOT)),
    )
    write_json(BEFORE_AGGREGATE, before_aggregate)
    write_json(AFTER_AGGREGATE, after_aggregate)

    gate2_check = gate2_runtime_field_check()
    gate3 = {
        "passed": all(
            source["after_metrics"][label]["survival_rate"] >= 0.05
            for label in WINDOW_LABELS
        ),
        "by_window": {
            label: {
                "signals_generated": source["after_metrics"][label][
                    "signals_generated"
                ],
                "signals_survived": source["after_metrics"][label][
                    "signals_survived"
                ],
                "survival_rate": source["after_metrics"][label]["survival_rate"],
            }
            for label in WINDOW_LABELS
        },
    }
    gate4 = source.get("gate4", {})

    readiness_row = find_readiness_row(readiness.get("readiness_report", []))
    oos_detail = readiness.get("sleeves", {}).get(SLEEVE_KEY, {})
    oos_trades = oos_detail.get("oos_trades") or []
    oos_concentration = positive_concentration(oos_trades)

    readiness_forward = (
        readiness.get("genuine_forward_rows_by_sleeve_dir", {}).get(SLEEVE_KEY, {})
    )
    current_state_summary = {
        "path": str(STATE_PATH.relative_to(ROOT)),
        "exists": STATE_PATH.exists(),
        "closed_position_count": len(state.get("closed_positions") or []),
        "open_position_count": len(state.get("open_positions") or []),
        "pending_entry_count": len(state.get("pending_entries") or []),
        "updated_at": state.get("updated_at"),
    }

    forward_closed_count = int(current_state_summary["closed_position_count"])
    forward_pnl_usd = float(readiness_forward.get("forward_pnl_usd", 0.0))
    forward_win_rate = None
    threshold_min_closed = int(DEFAULT_CONFIG["forward_gate_min_closed_trades"])
    threshold_min_win_rate = float(DEFAULT_CONFIG["forward_gate_min_win_rate"])
    threshold_max_share = float(
        DEFAULT_CONFIG["forward_gate_max_single_ticker_positive_share"]
    )
    threshold_max_hhi = float(DEFAULT_CONFIG["forward_gate_max_positive_hhi"])

    activation_checks = {
        "three_window_gate4_passed": bool(gate4.get("passed")),
        "gate2_runtime_fields_passed": gate2_check["passed"],
        "gate3_survival_passed": gate3["passed"],
        "shared_helper_parity_passed": bool(
            source.get("production_impact", {}).get("shared_policy_changed")
            and source.get("production_impact", {}).get("default_off_paper_only")
            and not source.get("production_impact", {}).get("production_orders_changed")
            and source.get("production_impact", {}).get("trade_enabled") is False
        ),
        "forward_min_closed_trades_passed": forward_closed_count
        >= threshold_min_closed,
        "forward_positive_net_pnl_passed": forward_closed_count > 0
        and forward_pnl_usd > 0.0,
        "forward_min_win_rate_passed": forward_win_rate is not None
        and forward_win_rate >= threshold_min_win_rate,
        "forward_concentration_evaluable": False,
        "forward_single_ticker_concentration_passed": False,
        "forward_hhi_passed": False,
        "oos_replay_positive_but_not_activation_evidence": bool(
            oos_detail.get("oos_closed_count", 0) > 0
            and oos_detail.get("oos_rv_spy_usd", 0) > 0
        ),
    }

    blockers = []
    if not activation_checks["three_window_gate4_passed"]:
        blockers.append("accepted_three_window_gate4_not_confirmed")
    if not activation_checks["gate2_runtime_fields_passed"]:
        blockers.append("runtime_entry_date_or_target_price_missing")
    if not activation_checks["gate3_survival_passed"]:
        blockers.append("survival_rate_below_5pct")
    if not activation_checks["shared_helper_parity_passed"]:
        blockers.append("shared_helper_or_default_off_parity_gap")
    if not activation_checks["forward_min_closed_trades_passed"]:
        blockers.append("forward_rows_immature")
    if not activation_checks["forward_positive_net_pnl_passed"]:
        blockers.append("forward_positive_pnl_not_proven")
    if not activation_checks["forward_min_win_rate_passed"]:
        blockers.append("forward_win_rate_not_proven")

    result = {
        "anti_js": "No JavaScript was used.",
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now_iso(),
        "lane": "alpha_search",
        "change_type": "activation_envelope",
        "changed_variable": "industry_relative_laggard_repair_live_activation_envelope_v1",
        "hypothesis": (
            "Industry-relative laggard repair has enough accepted three-window "
            "edge and OOS replay strength to justify live-realistic activation "
            "only if genuine production-forward rows meet the declared gate."
        ),
        "nearby_prior_experiments": [
            SOURCE_EXPERIMENT_ID,
            READINESS_EXPERIMENT_ID,
            "exp-20260611-020",
        ],
        "source_artifacts": {
            "accepted_shared_helper": str(SOURCE_ARTIFACT.relative_to(ROOT)),
            "post_acceptance_readiness": str(READINESS_ARTIFACT.relative_to(ROOT)),
            "before_aggregate": str(BEFORE_AGGREGATE.relative_to(ROOT)),
            "after_aggregate": str(AFTER_AGGREGATE.relative_to(ROOT)),
        },
        "gate1": {
            "baseline_protocol": "docs/backtesting.md fixed three-window accepted-stack baseline",
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "before_metrics": source["before_metrics"],
            "after_metrics": source["after_metrics"],
            "delta_metrics": source["delta_metrics"],
            "passed": True,
        },
        "gate2": {
            "runtime_open_positions_entry_date_target_price": gate2_check,
            "source_experiment_gate2": source.get("gate2"),
            "passed": gate2_check["passed"] and bool(source.get("gate2", {}).get("passed")),
        },
        "gate3": gate3,
        "gate4": {
            "source_experiment_gate4": gate4,
            "three_window_before_after_summary": {
                "before_expected_value_score_sum": before_aggregate[
                    "expected_value_score"
                ],
                "after_expected_value_score_sum": after_aggregate[
                    "expected_value_score"
                ],
                "expected_value_score_delta_sum": round(
                    after_aggregate["expected_value_score"]
                    - before_aggregate["expected_value_score"],
                    6,
                ),
                "before_total_pnl_sum": before_aggregate["total_pnl"],
                "after_total_pnl_sum": after_aggregate["total_pnl"],
                "total_pnl_delta_sum": round(
                    after_aggregate["total_pnl"] - before_aggregate["total_pnl"],
                    2,
                ),
                "windows_ev_improved": source["delta_metrics"]["aggregate"][
                    "windows_ev_improved"
                ],
                "windows_pnl_improved": source["delta_metrics"]["aggregate"][
                    "windows_pnl_improved"
                ],
                "target_trade_count_sum": source["delta_metrics"]["aggregate"][
                    "target_trade_count_sum"
                ],
            },
            "passed": bool(gate4.get("passed")),
        },
        "activation_envelope": {
            "decision": "rejected_activation_envelope_forward_immature",
            "blockers": blockers,
            "checks": activation_checks,
            "thresholds": {
                "forward_gate_min_closed_trades": threshold_min_closed,
                "forward_gate_min_win_rate": threshold_min_win_rate,
                "forward_gate_max_single_ticker_positive_share": threshold_max_share,
                "forward_gate_max_positive_hhi": threshold_max_hhi,
                "paper_notional_usd": DEFAULT_CONFIG["paper_notional_usd"],
                "daily_entry_slots": DEFAULT_CONFIG["daily_entry_slots"],
                "hold_days": DEFAULT_CONFIG["hold_days"],
                "same_ticker_cooldown_days": DEFAULT_CONFIG[
                    "same_ticker_cooldown_days"
                ],
                "min_avg_dollar_volume_20d": DEFAULT_CONFIG[
                    "min_avg_dollar_volume_20d"
                ],
            },
            "genuine_forward_from_readiness_artifact": readiness_forward,
            "current_production_state_summary": current_state_summary,
            "oos_replay_summary": {
                "readiness_bucket": readiness_row.get("readiness_bucket"),
                "oos_closed_count": oos_detail.get("oos_closed_count"),
                "oos_pnl_usd": oos_detail.get("oos_pnl_usd"),
                "oos_rv_cash_usd": oos_detail.get("oos_rv_cash_usd"),
                "oos_rv_spy_usd": oos_detail.get("oos_rv_spy_usd"),
                "oos_rv_qqq_usd": oos_detail.get("oos_rv_qqq_usd"),
                "oos_win_rate": oos_detail.get("oos_win_rate"),
                "oos_unique_tickers": oos_detail.get("oos_unique_tickers"),
                "oos_top_ticker_positive_pnl_share": oos_detail.get(
                    "oos_top_ticker_positive_pnl_share"
                ),
                "oos_positive_concentration": oos_concentration,
                "evidence_note": (
                    "OOS replay is useful as a lead, but it is not genuine "
                    "production-forward evidence and cannot activate live orders."
                ),
            },
            "live_realistic_envelope": {
                "trade_enabled": False,
                "orders_changed": False,
                "ranking_changed": False,
                "sizing_changed": False,
                "signal_logic_changed": False,
                "intended_order_semantics": (
                    "Keep observe-only paper ledger until forward gate passes; "
                    "future activation would use next-session-open entry and "
                    "10-trading-day exit from the shared helper."
                ),
                "capital_cap": (
                    "No live capital in this experiment. Candidate activation "
                    "would remain capped to $4,000 notional, one entry per day, "
                    "ADV >= $50M, and no core portfolio displacement without "
                    "a separate acceptance ticket."
                ),
                "kill_switch": (
                    "Do not enable live trading unless closed forward rows >= "
                    "60, net forward PnL > 0, win rate >= 50%, and positive PnL "
                    "concentration guards pass."
                ),
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "parity_note": (
                "This run is read-only and leaves the shared helper default-off. "
                "Positive OOS replay was not promoted because genuine forward "
                "production rows are still immature."
            ),
            "helper_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
        },
        "decision": "rejected_activation_envelope_forward_immature",
        "status": "rejected",
        "post_run_reflection": (
            "The alpha still looks economically interesting: Gate 1-4 accepted "
            "three-window evidence remains +0.2763 EV and +$6,208.99 with 306 "
            "target paper trades, and post-acceptance OOS replay shows 22 closed "
            "trades with +$5,132.36 RV vs SPY. The activation hypothesis fails "
            "because genuine production-forward evidence is 0 closed rows and "
            "one pending entry. Enabling live or default-on behavior here would "
            "convert replay-only evidence into a production decision and create "
            "the exact backtest/production inconsistency the protocol forbids."
        ),
        "next_retry_requires": (
            "At least 60 genuine closed production-forward rows for this shared "
            "helper, with positive net PnL, win rate >= 50%, and concentration "
            "guards passing. Do not retune thresholds, hold days, cooldown, slots, "
            "or notional as a near-neighbor retry."
        ),
        "related_files": [
            "quant/industry_relative_laggard_repair_paper_sleeve.py",
            "quant/test_industry_relative_laggard_repair_paper_sleeve.py",
            str(SOURCE_ARTIFACT.relative_to(ROOT)),
            str(READINESS_ARTIFACT.relative_to(ROOT)),
            str(STATE_PATH.relative_to(ROOT)),
        ],
    }
    write_json(OUTPUT_ARTIFACT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
