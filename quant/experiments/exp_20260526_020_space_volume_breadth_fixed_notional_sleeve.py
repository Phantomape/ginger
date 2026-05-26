"""exp-20260526-020: Space volume-breadth fixed-notional paper sleeve.

This alpha search tests one causal routing policy: admit the governed
full-history Space observation pool only into an additive, default-off,
fixed-notional paper sleeve when a free-OHLCV market volume-breadth thrust was
visible after the signal-date close and before the next-open paper entry.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260525_006_space_comm_arkx_confirmed_fixed_notional_sleeve as space_base
import exp_20260526_013_volume_breadth_breakout_sleeve as vbb


EXPERIMENT_ID = "exp-20260526-020"
STEM = "space_volume_breadth_fixed_notional_sleeve"
TRIAL_FAMILY = "governed_space_volume_breadth_fixed_notional_paper_sleeve"
CHANGED_VARIABLE = "space_governed_volume_breadth_fixed_notional_paper_sleeve_routing_v1"
RULE_VERSION = "space_volume_breadth_fixed_notional_paper_sleeve_v1"

TARGET_TICKERS = (
    "ASTS",
    "BKSY",
    "GSAT",
    "IRDM",
    "LUNR",
    "PL",
    "RDW",
    "RKLB",
    "SATS",
    "VSAT",
)
TARGET_SEGMENTS = {
    "satellite_connectivity",
    "launch_lunar",
    "space_data_defense",
}
TARGET_SECTOR_MAP = {
    "ASTS": "Communication Services",
    "BKSY": "Industrials",
    "GSAT": "Communication Services",
    "IRDM": "Communication Services",
    "LUNR": "Industrials",
    "PL": "Industrials",
    "RDW": "Industrials",
    "RKLB": "Industrials",
    "SATS": "Communication Services",
    "VSAT": "Communication Services",
}
RELATED_NON_CANDIDATES = ("ARKX", "UFO", "HAWK", "SPCE")

BASE_NOTIONAL_USD = 10_000.0
MIN_TARGET_TRADES = 8
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45

REPO_ROOT = space_base.REPO_ROOT
SOURCE_UNIVERSE_STATE = space_base.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = space_base.SOURCE_OHLCV_EXPERIMENT_ID
WINDOWS = space_base.WINDOWS
CANONICAL_WINDOWS = space_base.CANONICAL_WINDOWS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SPACE_BREADTH_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _load_snapshot(snapshot: str) -> dict[str, list[dict[str, Any]]]:
    payload = space_base.prior._load_json(REPO_ROOT / snapshot)
    return payload.get("ohlcv") or payload


def _target_universe() -> dict[str, Any]:
    state = space_base.prior._load_json(SOURCE_UNIVERSE_STATE)
    core = {str(ticker).upper() for ticker in state.get("core_trade_universe") or []}
    records = state.get("records") or {}
    selected: list[str] = []
    selected_records: dict[str, Any] = {}
    excluded: dict[str, list[str]] = {}

    for ticker in TARGET_TICKERS:
        record = records.get(ticker) or {}
        reasons: list[str] = []
        if not isinstance(record, dict):
            reasons.append("missing_universe_record")
            excluded[ticker] = reasons
            continue
        if record.get("history_class") != "full_history":
            reasons.append("not_full_history")
        if record.get("liquidity_tier") not in {"ok", "watch"}:
            reasons.append("liquidity_not_ok_or_watch")
        if record.get("status") not in {"research", "pilot"}:
            reasons.append("not_research_or_pilot")
        if record.get("theme_segment") not in TARGET_SEGMENTS:
            reasons.append("not_governed_space_segment")
        if ticker in core:
            reasons.append("already_core")

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

    for ticker in RELATED_NON_CANDIDATES:
        record = records.get(ticker) or {}
        reasons: list[str] = []
        if ticker in {"ARKX", "UFO"}:
            reasons.append("theme_beta_benchmark_not_trade_candidate")
        if ticker == "HAWK":
            reasons.append("short_history")
        if ticker == "SPCE":
            reasons.append("quarantine_meme")
        if ticker in core:
            reasons.append("already_core")
        excluded[ticker] = reasons or ["not_in_target_pool"]

    return {
        "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
        "as_of": state.get("as_of"),
        "selection_rule": (
            "target ticker in the governed Space observation list; record is "
            "research or pilot, theme_segment in satellite_connectivity, "
            "launch_lunar, or space_data_defense, liquidity_tier in {ok, watch}, "
            "history_class full_history, and not already in core"
        ),
        "why_this_cohort_is_not_noise": (
            "These are governed universe-state SPACE_CATALYST_SHADOW records "
            "with full observation-snapshot OHLCV history. ARKX and UFO are "
            "benchmarks only, HAWK is short-history, and SPCE is quarantined."
        ),
        "target_tickers": selected,
        "target_records": selected_records,
        "excluded_related_records": excluded,
    }


def _space_volume_breadth_confirmation(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    snapshot_map = _load_snapshot(snapshot)
    spy = space_base._load_close_series(snapshot, "SPY")
    base_universe = sorted(space_base.prior.get_universe())
    breadth_universe = sorted(set(base_universe) | set(space_base.TARGET_TICKERS))
    dates: set[str] = set()
    trade_as_of: dict[str, str | None] = {}

    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        entry_date = str(trade.get("entry_date") or "")
        as_of = space_base._previous_market_date(spy, entry_date)
        trade_as_of[key] = as_of
        if as_of:
            dates.add(as_of)

    breadth_by_date = vbb._breadth_context_by_date(
        snapshot_map,
        sorted(dates),
        breadth_universe,
    )
    passed_dates = [
        date
        for date, context in breadth_by_date.items()
        if context.get("volume_breadth_thrust_passed")
    ]
    snapshot_label = next(
        (label for label, spec in WINDOWS.items() if spec["snapshot"] == snapshot),
        snapshot,
    )
    SPACE_BREADTH_AUDIT[snapshot_label] = {
        "snapshot": snapshot,
        "trade_signal_dates_checked": len(dates),
        "volume_breadth_pass_dates_on_target_signal_dates": passed_dates,
        "breadth_universe_count": len(breadth_universe),
        "target_trade_count_before_breadth": len(trades),
    }

    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        as_of = trade_as_of.get(key)
        context = breadth_by_date.get(as_of or "") or {}
        out[key] = {
            "market_state_as_of": as_of,
            "rule_version": RULE_VERSION,
            "source_rule_version": vbb.RULE_VERSION,
            "known_at": "after_signal_date_close_before_next_open_paper_entry",
            "uses_free_ohlcv_only": True,
            "volume_breadth_context": context,
            "passed": bool(context.get("volume_breadth_thrust_passed")),
        }
    return out


def _configure_space_base() -> None:
    space_base.EXPERIMENT_ID = EXPERIMENT_ID
    space_base.STEM = STEM
    space_base.TRIAL_FAMILY = TRIAL_FAMILY
    space_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    space_base.TARGET_TICKERS = TARGET_TICKERS
    space_base.TARGET_SECTOR_MAP = TARGET_SECTOR_MAP
    space_base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    space_base.THEME_BENCHMARK_TICKER = "SPY"
    space_base.BROAD_BENCHMARK_TICKER = "SPY"
    space_base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    space_base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    space_base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    space_base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    space_base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    space_base.OUT_DIR = OUT_DIR
    space_base.OUT_JSON = OUT_JSON
    space_base.LOG_JSON = LOG_JSON
    space_base.TICKET_JSON = TICKET_JSON
    space_base.ARTIFACT_MD = ARTIFACT_MD
    space_base.EXPERIMENT_LOG = EXPERIMENT_LOG
    space_base._target_universe = _target_universe
    space_base._market_confirmation = _space_volume_breadth_confirmation


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_space_volume_breadth_fixed_notional_sleeve"
        if gate4_passed
        else "rejected_space_volume_breadth_fixed_notional_sleeve"
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
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
            "prior_trial_count": 9,
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "free_ohlcv_market_volume_breadth_internal_structure_field_on_"
                "governed_full_history_space_candidate_pool"
            ),
            "hypothesis": (
                "Governed full-history Space observation candidates may have "
                "replacement value when broad market up-volume participation "
                "confirms risk appetite on the signal date, but should remain "
                "default-off paper until forward replacement-value evidence exists."
            ),
            "backtest_protocol": {
                "source": (
                    "docs/backtesting.md three-window replay using exp-20260519-029 "
                    "observation-universe snapshots because canonical snapshots do "
                    "not fully cover the governed Space candidate pool"
                ),
                "windows": WINDOWS,
                "REGIME_AWARE_EXIT": True,
                "replay_llm": False,
                "replay_news": False,
            },
            "parameters": {
                "base_notional_usd": BASE_NOTIONAL_USD,
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
                "volume_breadth_source_experiment": "exp-20260526-013",
                "volume_breadth_rule_version": vbb.RULE_VERSION,
                "volume_breadth_thresholds": {
                    "min_volume_breadth_fraction": vbb.MIN_VOLUME_BREADTH_FRACTION,
                    "min_market_up_fraction": vbb.MIN_MARKET_UP_FRACTION,
                    "min_above_50d_fraction": vbb.MIN_ABOVE_50D_FRACTION,
                    "min_breadth_eligible_tickers": vbb.MIN_BREADTH_ELIGIBLE_TICKERS,
                    "candidate_volume_ratio_20": vbb.MIN_CANDIDATE_VOLUME_RATIO_20,
                },
                "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
                "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
                "locked_variables": [
                    "core signal rules",
                    "core ranking",
                    "core sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "production watchlists",
                    "live/default orders",
                    "VBB thresholds from exp-20260526-013",
                ],
                "anti_js": "No JavaScript was used.",
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "entry/candidate_pool/risk allocation: governed full-history "
                    "Space candidates may produce additive replacement value only "
                    "when broad market volume-breadth confirms risk appetite."
                ),
                "2_history_check": {
                    "exp-20260524-025_to_031": (
                        "Space comm/data/launch core-pool scouts mostly failed "
                        "window stability or concentration; this does not compete "
                        "for core slots."
                    ),
                    "exp-20260525-006": (
                        "Space comm ARKX-confirmed fixed-notional sleeve had only "
                        "+0.162 EV and failed window consistency/concentration."
                    ),
                    "exp-20260525-019": (
                        "Space launch/lunar strong-ARKX sleeve improved two "
                        "windows but failed sample and concentration, all positive "
                        "PnL from RKLB."
                    ),
                    "exp-20260526-013_and_014": (
                        "Market-wide volume-breadth breakout was accepted as "
                        "default-off paper; this imports its fixed source field "
                        "without retuning thresholds."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows, positive aggregate "
                    "EV/PnL, zero EV/PnL-regressed windows, >=8 target paper trades "
                    "across >=2 windows, drawdown drift <=0.5pp, survival >=5%, "
                    "and target concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260526_020_space_volume_breadth_fixed_notional_sleeve.py"
                ),
            },
            "space_volume_breadth_audit": SPACE_BREADTH_AUDIT,
            "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
            "production_impact": {
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
                    "A retained result is a research lead only. Promotion requires "
                    "a shared default-off Space paper adapter, daily report exposure, "
                    "forward replacement-value ledger, and parity tests before any "
                    "live/default behavior changes."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe Space semantic rows "
                "are sparse; skipped another ARKX/IWM/threshold/top-up retune after "
                "recent failures and meta-research freeze warnings. This tests a "
                "different production-visible free-OHLCV participation field on a "
                "governed full-history candidate pool."
            ),
            "interpretation": (
                "The Space volume-breadth fixed-notional paper route cleared the "
                "replay-only Gate 4 checks, but no production/shared policy was "
                "promoted. Treat this as a forward-watch sleeve lead, not a live "
                "capital change."
                if gate4_passed
                else (
                    "The Space volume-breadth fixed-notional paper route did not "
                    "clear Gate 4; do not promote it or retry nearby Space breadth "
                    "gates on the frozen sample without materially new forward "
                    "replacement-value evidence."
                )
            ),
            "next_evidence_needed": (
                "Build a shared default-off Space paper adapter with the exact "
                "volume-breadth field, daily report exposure, and forward "
                "replacement-value rows before any live/default behavior changes."
                if gate4_passed
                else (
                    "Forward replacement-value outcomes or a materially new Space "
                    "event-quality field; avoid nearby breadth/ETF retunes on these "
                    "frozen windows."
                )
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(EXPERIMENT_LOG),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "universe_state records.theme/theme_segment/status/liquidity_tier/history_class",
        "target OHLCV rows in all three exp-20260519-029 snapshots",
        "SPY prior-close OHLCV to identify signal-date close before next-open entry",
        "free-OHLCV volume/close/50-day context for breadth universe on signal date",
        "risk_engine.SECTOR_MAP target tickers patched from TARGET_SECTOR_MAP in replay",
    ]
    payload["gate2"]["ohlcv_coverage"]["note"] = (
        "Canonical snapshots do not fully cover the governed Space pool; the "
        "experiment therefore uses the same observation snapshots as prior Space "
        "candidate-pool experiments and records canonical coverage as a known limit."
    )
    payload["gate3"].update(
        {
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": space_base._round(min_survival, 4),
            "note": (
                "No new core filter or core entry rule was added. The target cohort "
                "is evaluated as additive default-off paper, so core survival is "
                "unchanged from the baseline replay."
            ),
        }
    )
    payload["gate4"].update(
        {
            "acceptance_rule": (
                "positive aggregate EV/PnL; zero EV/PnL-regressed windows; >=8 "
                "target trades across >=2 windows; drawdown drift <=0.5pp; "
                "survival >=5%; concentration guard passes"
            ),
            "aggregate_expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "aggregate_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        }
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
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
            f"# {EXPERIMENT_ID} Space Volume-Breadth Fixed-Notional Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the governed full-history Space observation pool into an additive fixed-notional default-off paper sleeve only when exp-20260526-013 market volume-breadth thrust is true on the signal date.",
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
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    space_base._write_json(OUT_JSON, payload)
    space_base._write_json(LOG_JSON, payload)
    space_base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space volume-breadth fixed-notional sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    space_base._write_text(ARTIFACT_MD, _build_report(payload))
    space_base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_space_base()
    payload = _customize_payload(space_base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            space_base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
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
