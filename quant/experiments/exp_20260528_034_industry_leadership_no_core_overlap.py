"""exp-20260528-034: no-core-overlap industry-leadership paper sleeve.

This alpha search tests one replacement-value discriminator on top of the
industry-leadership breadth breakout source from exp-20260527-022: keep only
default-off paper candidates that do not overlap with any same-day core A/B
entry. The goal is to test whether the candidate pool adds cleaner replacement
value when it is not duplicating the active core engine's signal day.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260527_022_industry_leadership_breadth_breakout_sleeve as source  # noqa: E402


EXPERIMENT_ID = "exp-20260528-034"
STEM = "industry_leadership_no_core_overlap"
TRIAL_FAMILY = "industry_leadership_no_core_overlap_candidate_pool"
CHANGED_VARIABLE = "industry_leadership_no_same_day_core_overlap_filter_v1"
RULE_VERSION = "industry_leadership_no_core_overlap_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260528_034_industry_leadership_no_core_overlap.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MIN_TARGET_TRADES = 30
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

OVERLAP_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


def _configure_base_module() -> None:
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
    base.MAX_PAPER_TRADES_PER_DAY = source.MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.shadow = source.ohlcv_helper
    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(source.ohlcv_helper, name):
            setattr(source.ohlcv_helper, name, None)


def _window_label(cfg: dict[str, str]) -> str:
    return next(
        (
            window_label
            for window_label, window_cfg in base.WINDOWS.items()
            if window_cfg is cfg
        ),
        str(cfg.get("start")),
    )


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> list[dict[str, Any]]:
    raw = source._candidate_rows_for_window(snapshot, cfg, universe, before_result)
    selected = [row for row in raw if not row.get("same_day_ab_overlap")]
    removed = [row for row in raw if row.get("same_day_ab_overlap")]
    label = _window_label(cfg)

    removed_industries = Counter(str(row.get("industry") or "Unknown") for row in removed)
    kept_industries = Counter(str(row.get("industry") or "Unknown") for row in selected)
    OVERLAP_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "raw_candidate_count": len(raw),
        "kept_candidate_count": len(selected),
        "removed_same_day_ab_overlap": len(removed),
        "removed_same_ticker_ab_overlap": sum(
            1 for row in removed if row.get("same_ticker_ab_overlap")
        ),
        "raw_candidate_days": len({row["date"] for row in raw}),
        "kept_candidate_days": len({row["date"] for row in selected}),
        "kept_unique_tickers": len({row["ticker"] for row in selected}),
        "removed_unique_tickers": len({row["ticker"] for row in removed}),
        "kept_top_industries": dict(kept_industries.most_common(10)),
        "removed_top_industries": dict(removed_industries.most_common(10)),
    }

    for row in selected:
        row["strategy"] = "industry_leadership_no_core_overlap"
        row["same_day_core_overlap_excluded"] = True
        row["no_core_overlap_rule_version"] = RULE_VERSION
        row["trade_enabled"] = False
        row["alters_orders"] = False
    return selected


def _update_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    decision = (
        "promising_replay_only_industry_leadership_no_core_overlap"
        if gate4_passed
        else "rejected_industry_leadership_no_core_overlap"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "Industry-leadership breadth breakout candidates should have cleaner "
        "replacement value when they do not overlap with any same-day core A/B "
        "entry. The single tested variable is the same-day core-overlap "
        "exclusion; source generation, ranking, notional, hold period, and "
        "execution model stay locked to exp-20260527-022."
    )
    payload["change_type"] = "default_off_paper_candidate_pool_replacement_value"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["prior_trial_count"] = 2
    payload["nearby_prior_experiments"] = [
        "exp-20260527-022",
        "exp-20260528-032",
    ]
    payload["multiple_testing_risk_bucket"] = "low"
    payload["new_evidence_type"] = "production_visible_core_overlap_replacement_value_field"
    payload["parameters"]["shadow_entry_filters"] = {
        **payload["parameters"]["shadow_entry_filters"],
        "source_experiment": "exp-20260527-022 industry-leadership breadth breakout",
        "added_filter": "same_day_ab_overlap must be false",
        "locked_source_thresholds": {
            "breakout_lookback_days": source.BREAKOUT_LOOKBACK_DAYS,
            "moving_average_days": source.MOVING_AVERAGE_DAYS,
            "return_lookback_days": source.RETURN_LOOKBACK_DAYS,
            "min_candidate_dollar_volume": source.MIN_CANDIDATE_DOLLAR_VOLUME,
            "min_candidate_volume_ratio_20": source.MIN_CANDIDATE_VOLUME_RATIO_20,
            "min_candidate_day_rs_vs_spy": source.MIN_CANDIDATE_DAY_RS_VS_SPY,
            "min_candidate_ret20_excess_spy": source.MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_industry_eligible_tickers": source.MIN_INDUSTRY_ELIGIBLE_TICKERS,
            "min_industry_leader_count": source.MIN_INDUSTRY_LEADER_COUNT,
            "min_industry_leadership_fraction": source.MIN_INDUSTRY_LEADERSHIP_FRACTION,
        },
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "industry_leadership_score desc",
        "ret20_excess_spy desc",
        "candidate_day_rs_vs_spy desc",
        "volume_ratio_20 desc",
        "dollar_volume desc",
        "ticker asc",
    ]
    payload["parameters"]["locked_variables"] = [
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
        "industry-leadership source thresholds from exp-20260527-022",
        "paper notional, next-open entry, and ten-trading-day exit",
    ]
    payload["parameters"]["acceptance"].update(
        {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "max_positive_hhi": MAX_POSITIVE_HHI,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: industry-leadership breakouts that do not "
            "duplicate same-day core A/B activity may add better replacement "
            "value than the raw industry-leadership source."
        ),
        "2_history_check": {
            "exp-20260527-022": (
                "Raw industry-leadership breadth breakout sleeve was rejected: "
                "aggregate EV/PnL were positive, but late_strong regressed. Its "
                "candidates already recorded same_day_ab_overlap and "
                "same_ticker_ab_overlap for this follow-up."
            ),
            "exp-20260528-032": (
                "Closed-ledger sector-breadth governor improved aggregate EV/PnL "
                "but was rejected because late_strong regressed. This run is not "
                "a governor and does not change core sizing or exits."
            ),
            "avoided_retreads": (
                "Skipped nearby Companyfacts, VBB/VCP, state-surface scalar, "
                "LLM soft-ranking, RS-line, sector-breadth governor, and AI "
                "optical close-location retunes per playbook, memory, and recent "
                "Gate 4 failures."
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
            "exp_20260528_034_industry_leadership_no_core_overlap.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "candidate ticker trailing 20/50-day OHLCV features",
        "same-date same-industry peer leadership counts",
        "same-day core A/B entries from baseline replay",
        "same_day_ab_overlap boolean recorded per candidate",
        "same_ticker_ab_overlap boolean recorded per candidate",
        "data/reference/broad_market_sector_map.json sector/industry/status rows",
        "SPY OHLCV Close rows for signal-day and trailing relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate2"]["note"] = (
        "The overlap filter uses only baseline replay entries on the same signal "
        "date plus same-day/trailing OHLCV and the existing offline industry map. "
        "Paper entry remains next open; no LLM or hidden future field is used."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The default-off paper "
        "candidate pool removes same-day core-overlap rows from the already "
        "paper-only industry-leadership source, so core survival is unchanged."
    )
    payload["industry_leadership_audit"] = source.INDUSTRY_AUDIT
    payload["core_overlap_audit"] = OVERLAP_AUDIT
    payload["why_not_other_changes"] = (
        "This run does alpha search rather than measurement repair because the "
        "three-window baseline, Gate 2 fields, and Gate 3 survival are readable. "
        "Data-limited LLM soft-ranking and nearby threshold/scalar retunes were "
        "skipped. The selected direction improves candidate-pool replacement "
        "value without adding noisy tickers."
    )
    payload["interpretation"] = (
        "The no-core-overlap industry-leadership sleeve cleared Gate 4 as a "
        "replay-only lead. It is still default-off paper only; production "
        "promotion requires a shared adapter and parity tests before any live "
        "or daily-report order behavior can change."
        if gate4_passed
        else (
            "The no-core-overlap industry-leadership sleeve did not clear Gate "
            "4. Do not promote it or retry nearby overlap/industry-threshold "
            "variants on these frozen windows without forward paper rows or a "
            "materially different free-data source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If revisited, collect forward paper rows or add an orthogonal "
        "production-visible source-quality field. Do not just retune "
        "same-industry thresholds or same-day overlap variants on the frozen "
        "sample."
    )
    payload["production_impact"]["promotion_requirement"] = (
        "A retained result would still require a shared default-off paper "
        "adapter, daily report exposure, forward replacement-value ledger, and "
        "parity tests before any live/default behavior changes."
    )
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(DOC_TICKET_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw | Kept | Removed overlap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["core_overlap_audit"].get(label, {})
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{trades} | {raw} | {kept} | {removed} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=audit.get("raw_candidate_count"),
                kept=audit.get("kept_candidate_count"),
                removed=audit.get("removed_same_day_ab_overlap"),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry-Leadership No-Core-Overlap Paper Sleeve",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: exclude industry-leadership paper candidates "
                "when any core A/B entry exists on the same signal date."
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
            "## Core-Overlap Audit",
            "",
            "```json",
            json.dumps(payload["core_overlap_audit"], indent=2, sort_keys=True),
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
        ]
    ) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "title": "Industry-leadership no-core-overlap paper sleeve",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "summary": payload["interpretation"],
    }


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    ticket = _ticket(payload)
    base._write_json(TICKET_JSON, ticket)
    base._write_json(DOC_TICKET_JSON, ticket)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_base_module()
    source.INDUSTRY_AUDIT.clear()
    OVERLAP_AUDIT.clear()
    base._candidate_rows_for_window = _candidate_rows_for_window
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
                    "core_overlap_audit": payload["core_overlap_audit"],
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
