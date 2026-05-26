"""exp-20260526-014: shared volume-breadth breakout paper adapter.

This alpha search promotes the positive exp-20260526-013 free-OHLCV replay lead
into a shared, production-visible default-off paper adapter. The single changed
variable is the shared adapter boundary and forward ledger/report exposure; the
volume-breadth, breakout, ranking, notional, entry, and exit definitions stay
fixed from exp-20260526-013.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260526_013_volume_breadth_breakout_sleeve as prior  # noqa: E402
from volume_breadth_breakout_paper_sleeve import (  # noqa: E402
    BREADTH_RULE_VERSION,
    DEFAULT_CONFIG,
    RULE_VERSION,
    build_volume_breadth_breakout_candidates,
)


EXPERIMENT_ID = "exp-20260526-014"
STEM = "volume_breadth_shared_adapter"
TRIAL_FAMILY = "volume_breadth_breakout_shared_paper_adapter"
CHANGED_VARIABLE = "volume_breadth_breakout_shared_default_off_paper_adapter_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"

REFERENCE_EXP013 = {
    "expected_value_score_delta_sum": 0.7124,
    "total_pnl_delta_sum": 13225.50,
    "target_trade_count": 47,
}

SHARED_ADAPTER_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _configure_prior_module() -> None:
    prior._configure_base_module()
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.BREATH_AUDIT = SHARED_ADAPTER_AUDIT
    prior.base.EXPERIMENT_ID = EXPERIMENT_ID
    prior.base.STEM = STEM
    prior.base.TRIAL_FAMILY = TRIAL_FAMILY
    prior.base.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.base.OUT_DIR = OUT_DIR
    prior.base.OUT_JSON = OUT_JSON
    prior.base.LOG_JSON = LOG_JSON
    prior.base.TICKET_JSON = TICKET_JSON
    prior.base.ARTIFACT_MD = ARTIFACT_MD
    prior.base.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.base._candidate_rows_for_window = _candidate_rows_for_window


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    entries_by_date = prior.ohlcv_helper._baseline_entries(before_result)
    dates = [
        date
        for date in prior.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    breadth_pass_dates: list[str] = []
    sample_breadth_context: dict[str, dict[str, Any]] = {}

    candidate_universe = {
        "status": "canonical_current_universe",
        "tickers": sorted(set(universe).intersection(snapshot)),
    }
    config = dict(DEFAULT_CONFIG)
    for date in dates:
        daily_candidates, _rejected, breadth = build_volume_breadth_breakout_candidates(
            as_of=date,
            ohlcv_by_ticker=snapshot,
            candidate_universe=candidate_universe,
            config=config,
        )
        if breadth.get("passed"):
            breadth_pass_dates.append(date)
            if len(sample_breadth_context) < 10:
                sample_breadth_context[date] = breadth
        for row in daily_candidates:
            ab_entries = entries_by_date.get(row["date"], [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            row["shared_adapter_rule_version"] = RULE_VERSION
            row["shared_breadth_rule_version"] = BREADTH_RULE_VERSION
            candidates.append(row)

    label = next(
        (
            window_label
            for window_label, window_cfg in prior.base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )
    SHARED_ADAPTER_AUDIT[label] = {
        "candidate_source_tickers": len(
            set(universe).intersection(snapshot).difference(prior.EXCLUDED_TICKERS)
        ),
        "trading_days": len(dates),
        "breadth_pass_days": len(breadth_pass_dates),
        "breadth_pass_day_fraction": prior.base._round(
            len(breadth_pass_dates) / len(dates) if dates else None,
            6,
        ),
        "raw_liquid_breadth_breakout_hits": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "sample_breadth_context": sample_breadth_context,
        "rule_version": RULE_VERSION,
        "breadth_rule_version": BREADTH_RULE_VERSION,
    }
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["volume_breadth_score"]),
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["volume_ratio_20"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    return candidates


def _adapter_replay_parity(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    trade_count = payload["target_trade_summary"]["total_trade_count"]
    ev_delta = float(aggregate["expected_value_score_delta_sum"])
    pnl_delta = float(aggregate["total_pnl_delta_sum"])
    checks = {
        "ev_delta_matches_exp013": abs(
            ev_delta - REFERENCE_EXP013["expected_value_score_delta_sum"]
        ) <= 0.0001,
        "pnl_delta_matches_exp013": abs(
            pnl_delta - REFERENCE_EXP013["total_pnl_delta_sum"]
        ) <= 0.01,
        "trade_count_matches_exp013": trade_count == REFERENCE_EXP013["target_trade_count"],
        "shared_rule_version_present": all(
            row.get("shared_adapter_rule_version") == RULE_VERSION
            for trades in payload["target_trades_by_window"].values()
            for row in trades
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "checks": checks,
        "failed": failed,
        "reference_experiment": "exp-20260526-013",
        "reference_metrics": REFERENCE_EXP013,
        "actual_metrics": {
            "expected_value_score_delta_sum": ev_delta,
            "total_pnl_delta_sum": pnl_delta,
            "target_trade_count": trade_count,
        },
    }


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    parity = _adapter_replay_parity(payload)
    payload["gate4"]["shared_adapter_replay_parity"] = parity
    payload["gate4"]["passed"] = bool(payload["gate4"]["passed"] and parity["passed"])
    decision = (
        "accepted_shared_volume_breadth_breakout_paper_adapter"
        if payload["gate4"]["passed"]
        else "rejected_shared_volume_breadth_breakout_paper_adapter"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["experiment_id"] = EXPERIMENT_ID
    payload["hypothesis"] = (
        "The positive exp-20260526-013 free-OHLCV volume-breadth breakout lead "
        "should be retained only if the exact rule can be moved into a shared "
        "default-off adapter that production can expose without changing live "
        "orders or creating backtest/production divergence."
    )
    payload["change_type"] = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 1
    payload["nearby_prior_experiments"] = [
        "exp-20260526-013",
        "exp-20260526-011",
        "exp-20260526-010",
        "exp-20260526-009",
        "exp-20260526-005",
        "exp-20260526-002",
    ]
    payload["multiple_testing_risk_bucket"] = "low"
    payload["new_evidence_type"] = (
        "positive_three_window_replay_plus_production_visible_shared_adapter"
    )
    payload["parameters"]["shared_adapter"] = {
        "module": "quant/volume_breadth_breakout_paper_sleeve.py",
        "rule_version": RULE_VERSION,
        "breadth_rule_version": BREADTH_RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
        "thresholds_changed_from_exp013": False,
    }
    payload["gate_questions"]["1_alpha_hypothesis"] = (
        "candidate_pool: keep the exp-20260526-013 volume-breadth breakout "
        "edge only as a shared production-visible paper adapter so forward "
        "replacement-value evidence can accumulate without live order changes."
    )
    payload["gate_questions"]["2_history_check"] = {
        "exp-20260526-013": (
            "Positive replay-only lead: aggregate EV +0.7124, PnL +$13,225.50, "
            "47 paper trades, 3/3 windows improved, concentration and DD passed."
        ),
        "recent_rejected_mechanical_sources": (
            "gap-and-hold, smooth momentum, undercut/reclaim, long-base, "
            "pocket-pivot, sector-leadership, and pullback-reclaim were rejected "
            "or anti-repeat constrained. This is not a threshold retune."
        ),
    }
    payload["gate_questions"]["3_single_causal_variable"] = CHANGED_VARIABLE
    payload["gate_questions"]["4_acceptance_standard"] = (
        "Same docs/backtesting.md three windows; reproduce exp-20260526-013 "
        "before/after overlay economics through the shared helper; add production "
        "and report exposure with trade_enabled=false; no live/default orders."
    )
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260526_014_volume_breadth_shared_adapter.py"
    )
    payload["volume_breadth_audit"] = SHARED_ADAPTER_AUDIT
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking and expectation-revision because current logs "
        "still show PIT/sample limits; skipped VCP/top-N and recent mechanical "
        "retunes due explicit playbook freezes. The strongest actionable alpha "
        "step is to make the already positive breadth edge production-visible "
        "and forward-auditable, not to mine another threshold."
    )
    payload["interpretation"] = (
        "Accepted: the shared volume-breadth breakout paper adapter reproduces "
        "the positive three-window exp-20260526-013 result and is wired as "
        "default-off paper only. It changes reporting/forward evidence only, "
        "not live orders."
        if payload["gate4"]["passed"]
        else (
            "Rejected: the shared adapter did not reproduce the exp-20260526-013 "
            "three-window evidence or failed a Gate 4 guardrail."
        )
    )
    payload["production_impact"] = {
        "shared_policy_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "parity_test_added": True,
        "default_off_paper_only": True,
        "production_watchlist_changed": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }
    payload["related_files"] = [
        prior.base._repo_rel(Path(__file__)),
        "quant/volume_breadth_breakout_paper_sleeve.py",
        "quant/run.py",
        "quant/report_generator.py",
        "quant/default_off_alpha_attribution.py",
        "quant/data_paths.py",
        "quant/test_volume_breadth_breakout_paper_sleeve.py",
        prior.base._repo_rel(OUT_JSON),
        prior.base._repo_rel(LOG_JSON),
        prior.base._repo_rel(TICKET_JSON),
        prior.base._repo_rel(ARTIFACT_MD),
        prior.base._repo_rel(EXPERIMENT_LOG),
    ]
    payload["next_evidence_needed"] = (
        "Collect closed forward paper outcomes and replacement value. Do not "
        "activate live capital or retune volume-breadth/breakout/volume thresholds "
        "without a separate Gate 1-4 experiment."
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Breadth days | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["volume_breadth_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {days} | {tickers} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                days=audit.get("breadth_pass_days"),
                tickers=audit.get("unique_candidate_tickers"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    parity = payload["gate4"]["shared_adapter_replay_parity"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Shared Volume-Breadth Breakout Paper Adapter",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: move the accepted replay definition into a shared "
                "default-off paper adapter with production/report exposure. The "
                "thresholds, top-1 ranking, $10k paper notional, next-open entry, "
                "and 10-trading-day close exit are unchanged from exp-20260526-013."
            ),
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
            "## Shared Adapter Parity",
            "",
            "```json",
            json.dumps(parity, indent=2, sort_keys=True),
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
                "Shared default-off paper adapter only. `run.py`, the daily report, "
                "and default-off attribution can expose the same helper output, but "
                "trade_enabled remains false and no live/default order path changes."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    prior.base._write_json(OUT_JSON, payload)
    prior.base._write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Shared volume-breadth breakout paper adapter",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": prior.base._repo_rel(ARTIFACT_MD),
        "json": prior.base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
    }
    prior.base._write_json(TICKET_JSON, ticket)
    prior.base._write_json(DOCS_TICKET_JSON, {**ticket, "owner": "alpha-search"})
    prior.base._write_text(ARTIFACT_MD, _build_report(payload))
    prior.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_prior_module()
    payload = _update_payload(prior.base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            prior.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": prior.base._repo_rel(ARTIFACT_MD),
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
