"""exp-20260527-903: Companyfacts growth + RS sector-exposure cap scout.

Alpha search. This retests the exp-20260527-017 free-data candidate source with
one structural diversification variable: while a default-off paper trade is
open, the sleeve cannot open another paper trade in the same sector. Core
entries, ranking, sizing, exits, LLM/news paths, watchlists, and orders are
unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260527_017_fundamental_growth_rs_candidate_pool as prev


EXPERIMENT_ID = "exp-20260527-903"
STEM = "fundamental_growth_rs_sector_exposure_cap"
TRIAL_FAMILY = "fundamental_growth_rs_default_off_candidate_pool"
CHANGED_VARIABLE = "fundamental_growth_rs_open_sector_exposure_cap_v1"
RULE_VERSION = "fundamental_growth_rs_sector_exposure_cap_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REFERENCE_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260527-017.json"
COOLDOWN_REFERENCE_JSON = REPO_ROOT / "experiments" / "logs" / "exp-20260527-018.json"

SECTOR_CAP_AUDIT: "OrderedDict[str, dict[str, Any]]" = OrderedDict()


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
    prev.base._candidate_rows_for_window = prev._candidate_rows_for_window
    prev.base._select_paper_trades = _select_paper_trades


def _window_label_for_candidates(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "unknown"
    dates = [str(row.get("date") or "") for row in candidates if row.get("date")]
    if not dates:
        return "unknown"
    first = min(dates)
    last = max(dates)
    for label, cfg in prev.base.WINDOWS.items():
        if str(cfg["start"]) <= first and last <= str(cfg["end"]):
            return label
    return "unknown"


def _select_paper_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    trading_date_index = {
        date: idx for idx, date in enumerate(prev.ohlcv_helper._trading_dates(snapshot))
    }
    active_sector_exit_index: dict[str, int] = {}
    label = _window_label_for_candidates(candidates)
    sector_cap_filtered = 0
    same_ticker_overlap_filtered = 0
    daily_limit_filtered = 0
    missing_trade_filtered = 0
    expired_sector_count = 0
    skipped_by_sector: Counter[str] = Counter()
    selected_by_sector: Counter[str] = Counter()

    for row in candidates:
        date = str(row.get("date") or "")
        sector = str(row.get("sector") or "Unknown")
        date_index = trading_date_index.get(date)
        entry_index = date_index + 1 if date_index is not None else None

        if entry_index is not None:
            expired = [
                active_sector
                for active_sector, exit_index in active_sector_exit_index.items()
                if entry_index > exit_index
            ]
            for active_sector in expired:
                expired_sector_count += 1
                active_sector_exit_index.pop(active_sector, None)

        if row.get("same_ticker_ab_overlap"):
            same_ticker_overlap_filtered += 1
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue

        active_exit_index = active_sector_exit_index.get(sector)
        if active_exit_index is not None and entry_index is not None and entry_index <= active_exit_index:
            sector_cap_filtered += 1
            skipped_by_sector[sector] += 1
            filtered.append(
                {
                    **row,
                    "filter_reason": "open_sector_exposure_cap",
                    "active_sector": sector,
                    "active_sector_exit_index": active_exit_index,
                    "candidate_entry_index": entry_index,
                    "sector_exposure_cap_rule_version": RULE_VERSION,
                }
            )
            continue

        if used_date_counts[date] >= prev.base.MAX_PAPER_TRADES_PER_DAY:
            daily_limit_filtered += 1
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue

        trade = prev.base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            missing_trade_filtered += 1
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue

        exit_index = trading_date_index.get(str(trade.get("exit_date") or ""))
        selected.append(
            {
                **trade,
                "sector_exposure_cap_rule_version": RULE_VERSION,
                "open_sector_exposure_cap_applied": True,
            }
        )
        selected_by_sector[sector] += 1
        used_date_counts[date] += 1
        if exit_index is not None:
            active_sector_exit_index[sector] = exit_index

    SECTOR_CAP_AUDIT[label] = {
        "rule_version": RULE_VERSION,
        "input_candidates": len(candidates),
        "selected_trades": len(selected),
        "selected_unique_tickers": len({str(row.get("ticker") or "").upper() for row in selected}),
        "selected_unique_sectors": len(selected_by_sector),
        "sector_cap_filtered": sector_cap_filtered,
        "same_ticker_core_overlap_filtered": same_ticker_overlap_filtered,
        "daily_top1_filtered": daily_limit_filtered,
        "missing_trade_filtered": missing_trade_filtered,
        "expired_sector_count": expired_sector_count,
        "selected_sector_counts": dict(sorted(selected_by_sector.items())),
        "skipped_sector_counts": dict(sorted(skipped_by_sector.items())),
        "selected_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in selected).items())
        ),
    }
    return selected, filtered


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


def _reference_comparison(payload: dict[str, Any], path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "reason": f"missing_{label}_reference"}
    reference = json.loads(path.read_text(encoding="utf-8"))
    ref_after = reference.get("after_metrics") or {}
    after = payload.get("after_metrics") or {}
    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for window_label in prev.base.WINDOWS:
        ref = ref_after.get(window_label) or {}
        cur = after.get(window_label) or {}
        by_window[window_label] = {
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
        "reference_experiment_id": reference.get("experiment_id"),
        "reference_decision": reference.get("decision"),
        "reference_gate4": reference.get("gate4"),
        "by_window_delta_after_vs_reference": by_window,
        "aggregate_delta_after_vs_reference": {
            "expected_value_score_delta_sum": prev.base._round(
                cur_agg["expected_value_score_sum"] - ref_agg["expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": prev.base._round(
                cur_agg["total_pnl_sum"] - ref_agg["total_pnl_sum"],
                2,
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
        "promising_replay_only_fundamental_growth_rs_sector_exposure_cap"
        if gate4_passed
        else "rejected_fundamental_growth_rs_sector_exposure_cap"
    )
    payload["status"] = decision
    payload["decision"] = decision
    payload["hypothesis"] = (
        "candidate_pool / entry: the exp-20260527-017 PIT SEC Companyfacts growth "
        "plus OHLCV RS source has strong gross alpha but failed drawdown and "
        "single-name concentration. A production-visible open-sector exposure cap "
        "may keep the edge while forcing same-day replacements away from the "
        "already-open sector, without retuning growth, RS, QQQ/SPY, cooldown, "
        "extension, notional, or hold-period thresholds."
    )
    payload["change_type"] = "fundamental_growth_rs_sector_exposure_cap_default_off_paper_sleeve"
    payload["mechanism_family"] = "free_sec_companyfacts_plus_ohlcv_rs_candidate_pool"
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = RULE_VERSION
    payload["prior_trial_count"] = 9
    payload["nearby_prior_experiments"] = [
        "exp-20260527-017",
        "exp-20260527-018",
        "exp-20260527-019",
        "exp-20260527-020",
        "exp-20260527-023",
    ]
    payload["multiple_testing_risk_bucket"] = "high"
    payload["new_evidence_type"] = "structural_sector_diversification_constraint_on_promising_candidate_source"
    payload["parameters"]["sector_exposure_cap"] = {
        "rule": "skip candidates whose sector already has an open paper trade in this sleeve",
        "active_window": "from next-open paper entry through 10-trading-day close exit",
        "replacement_behavior": "after a sector skip, same-day lower-ranked candidates remain eligible",
        "uses_future_data": False,
        "production_visible_state_needed": "paper sleeve open-trade ledger by sector",
    }
    payload["parameters"]["selection_rank"] = [
        "signal_date",
        "skip if candidate sector already has an open paper trade",
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
        "QQQ/SPY confirmation disabled",
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
            "candidate_pool / entry plus risk allocation: sector-level sleeve "
            "state can turn the strongest recent gross candidate-pool edge into a "
            "safer default-off paper source by reducing overlapping sector tails."
        ),
        "2_history_check": {
            "exp-20260527-017": (
                "Uncapped source improved all windows by aggregate EV +5.2015 "
                "and PnL +92488.83, but failed old_thin drawdown and APP "
                "single-name concentration."
            ),
            "exp-20260527-018": (
                "Ticker cooldown fixed concentration but regressed late_strong "
                "and drawdown still failed. This tests sector-open exposure, not "
                "another cooldown threshold."
            ),
            "exp-20260527-023": (
                "QQQ confirmation regressed late_strong and failed concentration. "
                "This keeps the source market-state neutral and changes only "
                "sleeve exposure state."
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
            "exp_20260527_903_fundamental_growth_rs_sector_exposure_cap.py"
        ),
    }
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "data/non_ohlcv/sec_companyfacts_selected_*.jsonl filed/end/fy/fp/value/canonical",
        "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
        "SPY OHLCV Close rows for RS proxy",
        "candidate sector from replay-visible sector map",
        "paper sleeve open-trade dates by sector for exposure-cap state",
    ]
    payload["gate2"]["note"] = (
        "SEC growth rows are filtered by filed <= signal_date. RS, trend, "
        "liquidity, and returns use signal-date or trailing OHLCV only. The "
        "sector cap uses only earlier selected paper trades and their known "
        "fixed-horizon paper exits in the same replay path."
    )
    payload["gate3"]["candidate_pool_changed"] = True
    payload["gate3"]["note"] = (
        "No core filter or live entry rule was added. The cap only changes "
        "default-off paper sleeve selection, so core survival is unchanged."
    )
    payload["sector_exposure_cap_audit"] = SECTOR_CAP_AUDIT
    payload["fundamental_growth_rs_audit"] = prev.FUNDAMENTAL_RS_AUDIT
    payload["reference_uncapped_exp17_comparison"] = _reference_comparison(
        payload,
        REFERENCE_JSON,
        "exp17_uncapped",
    )
    payload["reference_ticker_cooldown_exp18_comparison"] = _reference_comparison(
        payload,
        COOLDOWN_REFERENCE_JSON,
        "exp18_ticker_cooldown",
    )
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking, expectation revision, and Kova intraday "
        "because recent records show sparse or readiness-blocked attribution. "
        "Skipped VCP/VBB, state-surface, broad-market, QQQ/SPY, growth, RS, "
        "extension, and cooldown threshold retunes per playbook/memory freeze "
        "guidance. This run addresses the strongest current gross edge blocker "
        "with one structural exposure variable."
    )
    payload["interpretation"] = (
        "The sector-exposure-capped Companyfacts+RS sleeve cleared Gate 4 as a "
        "replay-only lead. It is still not live capital; promotion requires a "
        "shared default-off paper adapter, daily report exposure, forward "
        "replacement-value ledger, and parity tests."
        if gate4_passed
        else (
            "The sector-exposure-capped Companyfacts+RS sleeve did not clear "
            "Gate 4. Do not promote it or retry nearby Companyfacts+RS sector, "
            "ticker, growth, RS, QQQ/SPY, extension, top-N, notional, or hold "
            "thresholds on the frozen windows without forward rows or a "
            "materially new source-quality field."
        )
    )
    payload["next_evidence_needed"] = (
        "If positive, implement only as shared default-off paper before activation; "
        "if rejected, require forward rows or a new source-quality field, not a "
        "nearby sector/ticker/exposure or Companyfacts/RS threshold retune."
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
        "# exp-20260527-903 Fundamental Growth + RS Sector Exposure Cap",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: skip a Companyfacts-growth + OHLCV-RS paper "
            "candidate when the same sector already has an open paper trade in "
            "the sleeve; same-day lower-ranked candidates remain eligible."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Sector skips | Sectors | Tickers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prev.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["sector_exposure_cap_audit"].get(label, {})
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | "
            "{skips} | {sectors} | {tickers} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                skips=audit.get("sector_cap_filtered"),
                sectors=audit.get("selected_unique_sectors"),
                tickers=audit.get("selected_unique_tickers"),
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
            "## Sector Cap Audit",
            "",
            "```json",
            json.dumps(payload["sector_exposure_cap_audit"], indent=2, sort_keys=True),
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
        "title": "Fundamental growth + RS sector exposure cap scout",
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
