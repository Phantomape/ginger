"""exp-20260528-026: Space trend high-close fixed-notional paper sleeve.

This alpha search tests one causal routing policy: admit the governed
full-history Space observation pool into an additive, default-off,
fixed-notional paper sleeve only when the existing production signal engine
classified the discovery as ``trend_long`` and the signal day closed in the
top 16% of its intraday range.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260527_904_space_trend_only_fixed_notional_sleeve as trend_base


EXPERIMENT_ID = "exp-20260528-026"
STEM = "exp_20260528_026_space_trend_high_close_fixed_notional_sleeve"
TRIAL_FAMILY = "governed_space_trend_high_close_fixed_notional_paper_sleeve"
CHANGED_VARIABLE = (
    "space_governed_trend_high_close_fixed_notional_paper_sleeve_routing_v1"
)
RULE_VERSION = "space_trend_high_close_fixed_notional_paper_sleeve_v1"

TARGET_TICKERS = trend_base.TARGET_TICKERS
TARGET_SEGMENTS = trend_base.TARGET_SEGMENTS
TARGET_SECTOR_MAP = trend_base.TARGET_SECTOR_MAP
RELATED_NON_CANDIDATES = trend_base.RELATED_NON_CANDIDATES

BASE_NOTIONAL_USD = 10_000.0
TARGET_STRATEGY = "trend_long"
MIN_SIGNAL_DAY_CLOSE_LOCATION = 0.84
MIN_TARGET_TRADES = 6
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.45

space_base = trend_base.space_base
REPO_ROOT = trend_base.REPO_ROOT
SOURCE_UNIVERSE_STATE = trend_base.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = trend_base.SOURCE_OHLCV_EXPERIMENT_ID
WINDOWS = trend_base.WINDOWS
CANONICAL_WINDOWS = trend_base.CANONICAL_WINDOWS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = (
    REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
)
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / (
    f"{EXPERIMENT_ID}_space_trend_high_close_fixed_notional_sleeve.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _target_universe() -> dict[str, Any]:
    return trend_base._target_universe()


def _row_value(row: dict[str, Any], key: str) -> Any:
    return row.get(key) if key in row else row.get(key.capitalize())


def _load_snapshot(snapshot: str) -> dict[str, list[dict[str, Any]]]:
    payload = space_base.prior._load_json(REPO_ROOT / snapshot)
    return payload.get("ohlcv") or payload


def _signal_day_row(
    snapshot_map: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
) -> dict[str, Any] | None:
    rows = [
        row
        for row in snapshot_map.get(str(ticker or "").upper(), []) or []
        if isinstance(row, dict)
        and _row_value(row, "date")
        and str(_row_value(row, "date")) < entry_date
    ]
    if not rows:
        return None
    return max(rows, key=lambda row: str(_row_value(row, "date")))


def _close_location(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    try:
        high = float(_row_value(row, "high"))
        low = float(_row_value(row, "low"))
        close = float(_row_value(row, "close"))
    except (TypeError, ValueError):
        return None
    day_range = high - low
    if day_range <= 0:
        return None
    return max(0.0, min(1.0, (close - low) / day_range))


def _strategy_high_close_confirmation(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    snapshot_map = _load_snapshot(snapshot)
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")
        strategy = str(trade.get("strategy") or "")
        row = _signal_day_row(snapshot_map, ticker, entry_date)
        close_location = _close_location(row)
        strategy_passed = strategy == TARGET_STRATEGY
        high_close_passed = (
            close_location is not None
            and close_location >= MIN_SIGNAL_DAY_CLOSE_LOCATION
        )
        out[key] = {
            "rule_version": RULE_VERSION,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
            "uses_existing_signal_strategy_field": True,
            "uses_free_ohlcv_only": True,
            "strategy": strategy,
            "target_strategy": TARGET_STRATEGY,
            "signal_day": str(_row_value(row, "date")) if row else None,
            "signal_day_close_location_value": space_base._round(
                close_location,
                6,
            ),
            "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
            "strategy_passed": strategy_passed,
            "high_close_passed": high_close_passed,
            "passed": strategy_passed and high_close_passed,
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
    space_base._market_confirmation = _strategy_high_close_confirmation


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_default_off_space_trend_high_close_fixed_notional_sleeve"
        if gate4_passed
        else "rejected_space_trend_high_close_fixed_notional_sleeve"
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "registry_lane": "alpha_discovery",
            "status": decision,
            "decision": decision,
            "change_type": "candidate_pool_paper_sleeve_shadow",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "prior_trial_count": 11,
            "nearby_prior_experiments": [
                "exp-20260524-025",
                "exp-20260524-026",
                "exp-20260524-029",
                "exp-20260524-031",
                "exp-20260525-006",
                "exp-20260525-019",
                "exp-20260526-020",
                "exp-20260527-904",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "orthogonal_free_ohlcv_signal_day_close_location_field_on_"
                "governed_space_trend_candidate_pool"
            ),
            "hypothesis": (
                "Governed full-history Space observation candidates may have "
                "additive fixed-notional paper replacement value when the existing "
                "production signal engine marks the discovery trend_long and the "
                "signal day closes near the top of its own intraday range. This "
                "tests absorption/closing-demand quality without adding noisy "
                "tickers, ETF/breadth gates, LLM soft-ranking, scalars, or live "
                "Space slots."
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
                "target_strategy": TARGET_STRATEGY,
                "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
                "rule_version": RULE_VERSION,
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
                    "target governed Space ticker list",
                    "paper base notional",
                ],
                "anti_js": "No JavaScript was used.",
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "entry/candidate_pool/risk allocation: governed full-history "
                    "Space trend_long candidates may produce additive replacement "
                    "value when the signal day closes in the top 16% of its "
                    "intraday range."
                ),
                "2_history_check": {
                    "exp-20260525-006": (
                        "Space comm ARKX-confirmed sleeve failed stability and "
                        "concentration; this avoids ETF gates."
                    ),
                    "exp-20260526-020": (
                        "Full governed Space volume-breadth sleeve failed "
                        "late_strong and concentration; this avoids breadth gates."
                    ),
                    "exp-20260527-904": (
                        "Trend-only sleeve produced strong aggregate value but "
                        "failed old_thin and drawdown drift; this adds one OHLCV "
                        "absorption field to separate old_thin losers from better "
                        "trend candidates."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic rows and "
                        "closed same-theme replacement outcomes remain sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows, positive aggregate "
                    "EV/PnL, zero EV/PnL-regressed windows, >=6 target paper trades "
                    "across >=2 windows, drawdown drift <=0.5pp, survival >=5%, "
                    "and target concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260528_026_space_trend_high_close_fixed_notional_sleeve.py"
                ),
            },
            "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
            "production_impact": {
                "shared_policy_changed": gate4_passed,
                "backtester_adapter_changed": gate4_passed,
                "run_adapter_changed": gate4_passed,
                "replay_only": True,
                "parity_test_added": gate4_passed,
                "default_off_paper_only": True,
                "metadata_only": True,
                "production_field": "daily_close_location",
                "production_bucket": "space_trend_high_close_bucket",
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exits_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "Shared default-off Space observation metadata may be exposed "
                    "after a retained result, but live/default behavior still "
                    "requires a separate promotion experiment. Live Space slots "
                    "remain zero."
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe Space semantic rows "
                "remain sparse; skipped nearby ARKX/IWM/breadth retunes after "
                "recent failures and meta-research freeze warnings; skipped "
                "another direct core-pool expansion because recent Space cohorts "
                "failed window stability and concentration. This tests one free "
                "OHLCV field that production can compute before next-open paper "
                "entry."
            ),
            "interpretation": (
                "The Space trend high-close fixed-notional paper route cleared "
                "Gate 4 as a default-off observation-sleeve lead. It is not a "
                "live capital change; the production helper should expose the "
                "same close-location metadata with trade_enabled false."
                if gate4_passed
                else (
                    "The Space trend high-close fixed-notional paper route did "
                    "not clear Gate 4; do not promote it or retry nearby Space "
                    "price-action thresholds on the frozen sample without new "
                    "forward replacement evidence."
                )
            ),
            "next_evidence_needed": (
                "Expose the same close-location bucket in the shared default-off "
                "Space observation helper and collect forward replacement-value "
                "rows before any live/default behavior changes."
                if gate4_passed
                else (
                    "Forward replacement-value outcomes or a materially new Space "
                    "event-quality field; avoid nearby threshold retunes on these "
                    "frozen windows."
                )
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(DOCS_TICKET_JSON),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
                "quant/feature_layer.py",
                "quant/space_catalyst_sleeve.py",
                "quant/test_feature_layer.py",
                "quant/test_space_catalyst_sleeve.py",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "universe_state records.theme/theme_segment/status/liquidity_tier/history_class",
        "target OHLCV rows in all three exp-20260519-029 snapshots",
        "existing signal strategy field generated before next-open paper entry",
        "signal-day OHLCV high/low/close from previous market date before next-open paper entry",
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
                "positive aggregate EV/PnL; zero EV/PnL-regressed windows; >=6 "
                "target trades across >=2 windows; drawdown drift <=0.5pp; "
                "survival >=5%; concentration guard passes"
            ),
            "aggregate_expected_value_score_delta": aggregate[
                "expected_value_score_delta_sum"
            ],
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
            f"# {EXPERIMENT_ID} Space Trend High-Close Fixed-Notional Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: route the governed full-history Space observation pool into an additive fixed-notional default-off paper sleeve only when the existing signal engine labels the discovery `trend_long` and signal-day close-location is `>= 0.84`.",
            "",
            "## Gate Questions",
            "",
            f"- alpha_hypothesis: {payload['gate_questions']['1_alpha_hypothesis']}",
            f"- single_causal_variable: `{payload['gate_questions']['3_single_causal_variable']}`",
            f"- reproducibility: `{payload['gate_questions']['5_reproducibility']}`",
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
            "Gate-passing metadata is surfaced through the shared feature layer and default-off Space observation slot. Live Space slots remain zero, and no production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _registry_index_entry(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": ticket.get("status"),
        "lane": ticket.get("lane"),
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _update_registry_ticket(payload: dict[str, Any]) -> None:
    ticket = {}
    if DOCS_TICKET_JSON.exists():
        ticket = json.loads(DOCS_TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_discovery",
            "owner": "alpha-search-space",
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": EXPERIMENT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "prior_trial_count": payload["prior_trial_count"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(ARTIFACT_MD),
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "json": _repo_rel(OUT_JSON),
                "summary": payload["interpretation"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    DOCS_TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    DOCS_TICKET_JSON.write_text(
        json.dumps(space_base._safe(ticket), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    entry = _registry_index_entry(ticket)
    experiments = registry.setdefault("experiments", [])
    for index, existing in enumerate(experiments):
        if existing.get("experiment_id") == EXPERIMENT_ID:
            experiments[index] = {**existing, **entry}
            break
    else:
        experiments.append(entry)
    REGISTRY_JSON.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _persist(payload: dict[str, Any]) -> None:
    space_base._write_json(OUT_JSON, payload)
    space_base._write_json(LOG_JSON, payload)
    space_base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space trend high-close fixed-notional sleeve",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    space_base._write_text(ARTIFACT_MD, _build_report(payload))
    space_base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry_ticket(payload)


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
