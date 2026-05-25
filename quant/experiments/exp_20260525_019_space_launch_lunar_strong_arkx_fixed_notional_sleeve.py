"""exp-20260525-019: Space launch/lunar strong-ARKX fixed-notional sleeve.

Alpha search on one causal variable: route the governed Space launch/lunar
cohort into an additive, default-off, fixed-notional paper sleeve only when the
prior-close 20-day ARKX minus SPY momentum spread is at least 5 percentage
points.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260525_006_space_comm_arkx_confirmed_fixed_notional_sleeve as base


EXPERIMENT_ID = "exp-20260525-019"
STEM = "space_launch_lunar_strong_arkx_fixed_notional_sleeve"
TRIAL_FAMILY = "governed_space_launch_lunar_strong_arkx_fixed_notional_paper_sleeve"
CHANGED_VARIABLE = "space_launch_lunar_strong_arkx_fixed_notional_paper_sleeve_routing_v1"

TARGET_TICKERS = ("LUNR", "RKLB")
RELATED_TICKERS = ("ARKX", "UFO", "SPCE")
TARGET_SECTOR_MAP = {
    "LUNR": "Industrials",
    "RKLB": "Industrials",
}
TARGET_SEGMENT = "launch_lunar"

MIN_THEME_BENCHMARK_MOMENTUM_SPREAD = 0.05
MIN_TARGET_TRADES = 4
MIN_TARGET_WINDOWS = 2

REPO_ROOT = base.REPO_ROOT
SOURCE_UNIVERSE_STATE = base.SOURCE_UNIVERSE_STATE
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _target_universe() -> dict[str, Any]:
    state = base.prior._load_json(SOURCE_UNIVERSE_STATE)
    core = {str(ticker).upper() for ticker in state.get("core_trade_universe") or []}
    records = state.get("records") or {}
    selected: list[str] = []
    selected_records: dict[str, Any] = {}
    excluded: dict[str, list[str]] = {}

    for ticker in TARGET_TICKERS + RELATED_TICKERS:
        record = records.get(ticker) or {}
        reasons: list[str] = []
        if not isinstance(record, dict):
            reasons.append("missing_universe_record")
            excluded[ticker] = reasons
            continue
        if record.get("theme_segment") != TARGET_SEGMENT:
            reasons.append("not_launch_lunar_segment")
        if record.get("status") != "research":
            reasons.append("not_research_status")
        if record.get("history_class") != "full_history":
            reasons.append("not_full_history")
        if record.get("liquidity_tier") not in {"ok", "watch"}:
            reasons.append("liquidity_not_ok_or_watch")
        if ticker in core:
            reasons.append("already_core")
        if ticker not in TARGET_TICKERS:
            reasons.append("related_benchmark_or_quarantine_not_target")

        if reasons:
            excluded[ticker] = reasons
            continue

        selected.append(ticker)
        selected_records[ticker] = {
            key: record.get(key)
            for key in (
                "status",
                "theme",
                "theme_segment",
                "liquidity_tier",
                "history_class",
                "first_trade_allowed_as_of",
                "max_capital_scalar",
                "max_risk_scalar",
                "requires_event_guard",
                "event_guard_profile",
                "pilot_sleeve",
                "source",
                "source_reason",
                "notes",
            )
        }
        selected_records[ticker]["sector_patch"] = TARGET_SECTOR_MAP[ticker]

    return {
        "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
        "as_of": state.get("as_of"),
        "selection_rule": (
            "target ticker in LUNR/RKLB; record is research, liquidity_tier in "
            "{ok, watch}, history_class full_history, theme_segment launch_lunar, "
            "and not already in core. ARKX/UFO/SPCE are not trade candidates."
        ),
        "why_this_cohort_is_not_noise": (
            "These are governed universe-state Space launch/lunar records with "
            "full observation-snapshot OHLCV history and explicit event-guard "
            "profiles. ARKX is used only as a free prior-close same-theme market "
            "confirmation field."
        ),
        "target_tickers": selected,
        "target_records": selected_records,
        "excluded_related_records": excluded,
    }


def _apply_overrides() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.TARGET_TICKERS = TARGET_TICKERS
    base.TARGET_SECTOR_MAP = TARGET_SECTOR_MAP
    base.MIN_THEME_BENCHMARK_MOMENTUM_SPREAD = MIN_THEME_BENCHMARK_MOMENTUM_SPREAD
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base._target_universe = _target_universe


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_space_launch_lunar_strong_arkx_fixed_notional_sleeve"
        if gate4_passed
        else "rejected_space_launch_lunar_strong_arkx_fixed_notional_sleeve"
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "change_type": "candidate_pool_paper_sleeve_shadow",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "prior_trial_count": 7,
            "nearby_prior_experiments": [
                "exp-20260512-032",
                "exp-20260524-031",
                "exp-20260525-006",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "free_same_theme_arkx_minus_spy_prior_close_momentum_spread_for_"
                "governed_space_launch_lunar_candidate_pool"
            ),
            "hypothesis": (
                "Governed Space launch/lunar candidates should only be tracked as "
                "additive fixed-notional paper when same-theme ARKX momentum leads "
                "SPY by at least 5 percentage points, because ordinary Space beta "
                "confirmation did not protect the communications pool."
            ),
        }
    )
    payload["parameters"].update(
        {
            "target_tickers": list(TARGET_TICKERS),
            "target_segment": TARGET_SEGMENT,
            "target_sector_map": TARGET_SECTOR_MAP,
            "min_theme_broad_momentum_spread": MIN_THEME_BENCHMARK_MOMENTUM_SPREAD,
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": 2,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": base.MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": base.MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": base.MAX_POSITIVE_HHI,
            },
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool/risk allocation: governed Space launch/lunar "
            "records may have additive paper replacement value only during strong "
            "same-theme ARKX leadership versus SPY."
        ),
        "2_history_check": {
            "exp-20260524-031": (
                "Direct launch/lunar core-pool admission failed aggregate EV/PnL, "
                "drawdown, sample, and concentration despite positive RKLB target PnL."
            ),
            "exp-20260525-006": (
                "Space communications ARKX non-lagging fixed-notional sleeve failed "
                "with EV/PnL-regressed windows and concentration; this tests a "
                "different launch/lunar cohort and a stronger 5pp ARKX leadership gate."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three docs/backtesting.md windows, positive aggregate EV/PnL, "
            ">=2 EV-improved windows, zero EV/PnL-regressed windows, >=4 target "
            "paper trades across >=2 windows, drawdown drift <=0.5pp, survival "
            ">=5%, and target concentration inside guardrails."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe quant\\experiments\\"
            "exp_20260525_019_space_launch_lunar_strong_arkx_fixed_notional_sleeve.py"
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "default_off_paper_only": True,
        "production_watchlist_changed": False,
        "production_orders_changed": False,
        "trade_enabled": False,
        "promotion_requirement": (
            "A retained result would still require a shared default-off Space "
            "launch/lunar paper adapter, daily report exposure, forward "
            "replacement-value ledger, and parity tests before any live/default "
            "behavior changes."
        ),
    }
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because replay-safe historical attribution is "
        "sparse; skipped additional Space risk scalars because risk_scalar_or_topup "
        "is a meta-research freeze candidate; skipped the already rejected Space "
        "comm/satcom and data/defense candidate pools. This tests one "
        "production-visible same-theme benchmark state on a governed launch/lunar "
        "paper route."
    )
    payload["interpretation"] = (
        "The strong-ARKX launch/lunar fixed-notional paper route cleared the "
        "replay-only Gate 4 checks, but no shared policy was promoted."
        if gate4_passed
        else (
            "The strong-ARKX launch/lunar fixed-notional paper route did not clear "
            "Gate 4; Space launch/lunar still needs forward replacement-value rows "
            "or a materially stronger mission/contract-quality field before promotion."
        )
    )
    if not gate4_passed and not payload.get("rejection_reason"):
        payload["rejection_reason"] = "Gate 4 failed"
    payload["next_evidence_needed"] = (
        "Forward launch/lunar replacement-value rows or a materially stronger "
        "mission/contract-quality field; do not retune ARKX thresholds on the "
        "same frozen sample."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(EXPERIMENT_LOG),
    ]
    payload["anti_js"] = "No JavaScript was used."
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {filtered} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                filtered=len(payload["filtered_out_target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Space Launch/Lunar Strong-ARKX Fixed-Notional Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the governed launch/lunar Space cohort into an additive fixed-notional default-off paper sleeve only when prior-close ARKX 20d momentum leads SPY by at least 5 percentage points.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}`",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}`",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space launch/lunar strong-ARKX fixed-notional sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _apply_overrides()
    payload = _patch_payload(base._build_payload())
    persist(payload)
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
