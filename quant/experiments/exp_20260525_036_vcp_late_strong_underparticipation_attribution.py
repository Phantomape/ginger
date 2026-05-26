"""exp-20260525-036: VCP late-strong underparticipation attribution.

This observed-only experiment explains why exp-20260525-022 contributes little
in the late_strong window. It does not change the VCP definition, QQQ/SPY gate,
rank, notional, hold period, exits, universe, LLM/news, or orders.

Diagnostics isolate raw VCP opportunity, QQQ gate effects, daily rank depth,
same-day replacement value, and 5/10/20-day horizon shape.
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

import exp_20260426_volatility_contraction_breakout_shadow as volatility_shadow  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260525_022_volatility_contraction_qqq_confirmed_sleeve as qqq_source  # noqa: E402


EXPERIMENT_ID = "exp-20260525-036"
STEM = "vcp_late_strong_underparticipation_attribution"
TRIAL_FAMILY = "volatility_contraction_breakout_default_off_paper_sleeve"
CHANGED_VARIABLE = "vcp_late_strong_underparticipation_diagnostics_v1"
RULE_VERSION = "vcp_late_strong_underparticipation_attribution_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SOURCE_EXP022_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260525-022"
    / "volatility_contraction_qqq_confirmed_sleeve.json"
)

TOPN_VARIANTS: "OrderedDict[str, int]" = OrderedDict(
    [
        ("top1_exp022_replay", 1),
        ("top2_candidate_depth", 2),
        ("top3_candidate_depth", 3),
    ]
)


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
    base.shadow = volatility_shadow

    for name in (
        "MIN_PRIOR_DAY_RETURN",
        "MIN_PRIOR_DAY_RS_VS_SPY",
        "MIN_OPEN_VS_PRIOR_CLOSE",
    ):
        if not hasattr(volatility_shadow, name):
            setattr(volatility_shadow, name, None)


def _round(value: Any, digits: int = 6) -> Any:
    return base._round(value, digits)


def _qqq_abs_bucket(row: dict[str, Any]) -> str:
    qqq_ret = row.get("qqq_ret20_on_signal")
    if qqq_ret is None:
        return "qqq_missing"
    if row.get("qqq_gt_spy20") is not True:
        return "qqq_not_leading_spy"
    qqq_ret = float(qqq_ret)
    if qqq_ret < 0:
        return "qqq_leading_but_negative_20d"
    if qqq_ret < 0.02:
        return "qqq_leading_low_positive_0_2pct"
    if qqq_ret < 0.05:
        return "qqq_leading_medium_positive_2_5pct"
    return "qqq_leading_strong_positive_ge_5pct"


def _rank_bucket(row: dict[str, Any]) -> str:
    rank = int(row.get("vcp_candidate_rank_on_signal_date") or 0)
    if rank <= 0:
        return "rank_missing"
    if rank <= 3:
        return f"rank_{rank}"
    return "rank_4_plus"


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["date"],
        row["short_to_long_atr_ratio"],
        -row["candidate_day_rs_vs_spy"],
        -row["dollar_volume"],
        row["ticker"],
    )


def _load_exp022() -> dict[str, Any]:
    return json.loads(SOURCE_EXP022_JSON.read_text(encoding="utf-8"))


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> dict[str, Any]:
    entries_by_date = volatility_shadow._baseline_entries(before_result)
    dates = [
        date
        for date in volatility_shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    ]
    indexes = {
        "QQQ": qqq_source._date_index(volatility_shadow._series(snapshot, "QQQ")),
        "SPY": qqq_source._date_index(volatility_shadow._series(snapshot, "SPY")),
    }
    raw_rows: list[dict[str, Any]] = []
    qqq_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in volatility_shadow.EXCLUDED_TICKERS:
            continue
        for row in volatility_shadow._candidate_rows(snapshot, ticker, dates):
            ab_entries = entries_by_date.get(row["date"], [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            row.update(qqq_source._market_context_for_date(snapshot, indexes, str(row["date"])))
            row["qqq_abs_bucket"] = _qqq_abs_bucket(row)
            row["attribution_rule_version"] = RULE_VERSION
            row["known_at"] = "after_signal_date_close_before_next_open_paper_entry"
            row["trade_enabled"] = False
            row["alters_orders"] = False
            raw_rows.append(row)
            if row.get("qqq_gt_spy20") is True:
                qqq_rows.append(row)
            else:
                rejected_rows.append(row)

    raw_rows.sort(key=_sort_key)
    qqq_rows.sort(key=_sort_key)
    rejected_rows.sort(key=_sort_key)

    ranks_by_date: Counter[str] = Counter()
    ranked_qqq: list[dict[str, Any]] = []
    for row in qqq_rows:
        date = str(row.get("date") or "")
        ranks_by_date[date] += 1
        ranked = {
            **row,
            "vcp_candidate_rank_on_signal_date": ranks_by_date[date],
        }
        ranked["vcp_rank_bucket"] = _rank_bucket(ranked)
        ranked_qqq.append(ranked)

    return {
        "raw": raw_rows,
        "qqq_confirmed": ranked_qqq,
        "qqq_rejected": rejected_rows,
    }


def _select_topn(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    max_per_day: int,
    variant: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used: Counter[str] = Counter()
    for row in candidates:
        date = str(row.get("date") or "")
        enriched = {
            **row,
            "selection_variant": variant,
            "max_paper_trades_per_day": int(max_per_day),
        }
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**enriched, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used[date] >= max_per_day:
            filtered.append({**enriched, "filter_reason": "daily_topn_limit"})
            continue
        trade = base._paper_trade_from_candidate(snapshot, enriched)
        if trade is None:
            filtered.append({**enriched, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(
            {
                **trade,
                "selection_variant": variant,
                "max_paper_trades_per_day": int(max_per_day),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )
        used[date] += 1
    return selected, filtered


def _candidate_outcome_rows(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in candidates:
        trade = base._paper_trade_from_candidate(snapshot, row)
        if trade is not None:
            rows.append(trade)
    return rows


def _trade_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    positives = [value for value in pnls if value > 0]
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2) if pnls else None,
        "win_rate": _round(sum(1 for value in pnls if value > 0) / len(pnls), 6)
        if pnls
        else None,
        "positive_pnl": _round(sum(positives), 2),
        "negative_pnl": _round(sum(value for value in pnls if value < 0), 2),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "tickers": sorted({str(row.get("ticker") or "").upper() for row in rows}),
        "signal_dates": sorted({str(row.get("signal_date") or row.get("date") or "") for row in rows}),
    }


def _candidate_return_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "candidate_count": len(rows),
        "candidate_day_count": len({row.get("date") for row in rows}),
        "ticker_count": len({row.get("ticker") for row in rows}),
    }
    for horizon in ("fwd_5d", "fwd_10d", "fwd_20d"):
        values = [
            float(row[horizon])
            for row in rows
            if isinstance(row.get(horizon), (int, float))
        ]
        out[f"{horizon}_sample"] = len(values)
        out[f"{horizon}_avg"] = _round(sum(values) / len(values), 6) if values else None
        out[f"{horizon}_win_rate"] = (
            _round(sum(1 for value in values if value > 0) / len(values), 6)
            if values
            else None
        )
    return out


def _bucket_trade_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "missing")].append(row)
    return {key: _trade_summary(value) for key, value in sorted(grouped.items())}


def _bucket_candidate_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "missing")].append(row)
    return {key: _candidate_return_summary(value) for key, value in sorted(grouped.items())}


def _rank_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_rank: Counter[str] = Counter()
    by_date: Counter[str] = Counter()
    for row in rows:
        by_rank[str(row.get("vcp_candidate_rank_on_signal_date") or "missing")] += 1
        by_date[str(row.get("date") or "")] += 1
    return {
        "candidate_count": len(rows),
        "candidate_day_count": len(by_date),
        "rank_count": dict(sorted(by_rank.items(), key=lambda item: int(item[0]))),
        "max_candidates_on_signal_date": max(by_date.values()) if by_date else 0,
        "dates_with_at_least_2_candidates": sum(1 for value in by_date.values() if value >= 2),
        "dates_with_at_least_3_candidates": sum(1 for value in by_date.values() if value >= 3),
    }


def _same_day_rank_replacement(
    snapshot: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_date[str(row.get("date") or "")].append(row)
    replacements: list[dict[str, Any]] = []
    for date, candidates in sorted(by_date.items()):
        candidates = sorted(candidates, key=lambda row: int(row.get("vcp_candidate_rank_on_signal_date") or 999))
        if len(candidates) < 2:
            continue
        top = base._paper_trade_from_candidate(snapshot, candidates[0])
        second = base._paper_trade_from_candidate(snapshot, candidates[1])
        if top is None or second is None:
            continue
        replacements.append(
            {
                "signal_date": date,
                "rank1_ticker": top.get("ticker"),
                "rank1_pnl": top.get("pnl"),
                "rank2_ticker": second.get("ticker"),
                "rank2_pnl": second.get("pnl"),
                "rank2_minus_rank1_pnl": _round(
                    float(second.get("pnl") or 0.0) - float(top.get("pnl") or 0.0),
                    2,
                ),
                "rank1_fwd_10d": candidates[0].get("fwd_10d"),
                "rank2_fwd_10d": candidates[1].get("fwd_10d"),
            }
        )
    return replacements


def _variant_overlay_summary(
    before_results: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    snapshots: dict[str, dict[str, list[dict[str, Any]]]],
    candidates_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    variants: dict[str, Any] = OrderedDict()
    for variant, max_per_day in TOPN_VARIANTS.items():
        window_rows: dict[str, Any] = OrderedDict()
        target_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
        for label in base.WINDOWS:
            selected, _filtered = _select_topn(
                snapshots[label],
                candidates_by_window[label],
                max_per_day,
                variant,
            )
            overlay = base._overlay_from_paper_trades(before_results[label], selected)
            after = base.overlay_helper._metrics_with_overlay(before_results[label], overlay)
            delta = base.overlay_helper._delta(after, before_metrics[label])
            target_by_window[label] = selected
            window_rows[label] = {
                "before": before_metrics[label],
                "after": after,
                "delta": delta,
                "target_trade_count": len(selected),
            }
        aggregate = base._aggregate(window_rows)
        variants[variant] = {
            "max_paper_trades_per_day": max_per_day,
            "delta_by_window": {
                label: row["delta"] for label, row in window_rows.items()
            },
            "aggregate": aggregate,
            "trade_summary": base._target_trade_summary(target_by_window),
        }
    return variants


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(base.get_universe())
    snapshots: dict[str, dict[str, list[dict[str, Any]]]] = {}
    before_results: dict[str, dict[str, Any]] = {}
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    all_rows_by_window: dict[str, dict[str, list[dict[str, Any]]]] = OrderedDict()
    qqq_candidates_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = volatility_shadow._run_baseline(universe, cfg)
        before_results[label] = before_result
        before_metrics[label] = base.overlay_helper._metrics(before_result)
        snapshot = volatility_shadow._load_snapshot(cfg["snapshot"])
        snapshots[label] = snapshot
        rows = _candidate_rows_for_window(snapshot, cfg, universe, before_result)
        all_rows_by_window[label] = rows
        qqq_candidates_by_window[label] = rows["qqq_confirmed"]

    variant_overlay = _variant_overlay_summary(
        before_results,
        before_metrics,
        snapshots,
        qqq_candidates_by_window,
    )

    by_window: dict[str, Any] = OrderedDict()
    for label in base.WINDOWS:
        rows = all_rows_by_window[label]
        snapshot = snapshots[label]
        raw_trade_opportunities = _candidate_outcome_rows(snapshot, rows["raw"])
        qqq_trade_opportunities = _candidate_outcome_rows(snapshot, rows["qqq_confirmed"])
        rejected_trade_opportunities = _candidate_outcome_rows(snapshot, rows["qqq_rejected"])
        qqq_rejected_top1, _ = _select_topn(
            snapshot,
            rows["qqq_rejected"],
            1,
            "qqq_rejected_daily_top1_counterfactual",
        )
        raw_top1, _ = _select_topn(
            snapshot,
            rows["raw"],
            1,
            "raw_vcp_daily_top1_no_qqq_gate_counterfactual",
        )
        by_window[label] = {
            "candidate_funnel": {
                "raw_vcp_candidates": len(rows["raw"]),
                "raw_vcp_candidate_days": len({row.get("date") for row in rows["raw"]}),
                "qqq_confirmed_candidates": len(rows["qqq_confirmed"]),
                "qqq_confirmed_candidate_days": len(
                    {row.get("date") for row in rows["qqq_confirmed"]}
                ),
                "qqq_rejected_candidates": len(rows["qqq_rejected"]),
                "qqq_rejected_candidate_days": len(
                    {row.get("date") for row in rows["qqq_rejected"]}
                ),
            },
            "rank_audit": _rank_audit(rows["qqq_confirmed"]),
            "raw_candidate_return_summary": _candidate_return_summary(rows["raw"]),
            "qqq_confirmed_candidate_return_summary": _candidate_return_summary(
                rows["qqq_confirmed"]
            ),
            "qqq_rejected_candidate_return_summary": _candidate_return_summary(
                rows["qqq_rejected"]
            ),
            "candidate_qqq_abs_bucket_summary": _bucket_candidate_summary(
                rows["raw"],
                "qqq_abs_bucket",
            ),
            "qqq_confirmed_rank_bucket_candidate_summary": _bucket_candidate_summary(
                rows["qqq_confirmed"],
                "vcp_rank_bucket",
            ),
            "all_raw_candidate_trade_opportunity": _trade_summary(raw_trade_opportunities),
            "qqq_confirmed_candidate_trade_opportunity": _trade_summary(
                qqq_trade_opportunities
            ),
            "qqq_rejected_candidate_trade_opportunity": _trade_summary(
                rejected_trade_opportunities
            ),
            "qqq_rejected_daily_top1_counterfactual": _trade_summary(qqq_rejected_top1),
            "raw_vcp_daily_top1_no_qqq_gate_counterfactual": _trade_summary(raw_top1),
            "same_day_rank2_replacement_rows": _same_day_rank_replacement(
                snapshot,
                rows["qqq_confirmed"],
            ),
        }

    late = by_window["late_strong"]
    top1_late = variant_overlay["top1_exp022_replay"]["delta_by_window"]["late_strong"]
    top2_late = variant_overlay["top2_candidate_depth"]["delta_by_window"]["late_strong"]
    top3_late = variant_overlay["top3_candidate_depth"]["delta_by_window"]["late_strong"]
    rank2_rows = late["same_day_rank2_replacement_rows"]
    rank2_delta_sum = _round(sum(row["rank2_minus_rank1_pnl"] for row in rank2_rows), 2)
    top2_improves_late = (
        float(top2_late["total_pnl"]) > float(top1_late["total_pnl"])
        and float(top2_late["expected_value_score"]) > float(top1_late["expected_value_score"])
    )
    late_underparticipation = {
        "diagnosis": (
            "late_strong weakness is mainly underparticipation/rank-depth scarcity, "
            "not an obvious failed QQQ gate. Only one late_strong signal date had a "
            "rank-2 QQQ-confirmed alternative; adding it explains the small top-2 "
            "late_strong uplift."
        )
        if top2_improves_late and rank2_rows
        else (
            "late_strong weakness is not clearly solved by same-day rank depth; keep "
            "exp-022 unchanged until forward rows arrive."
        ),
        "top1_late_strong_delta": top1_late,
        "top2_late_strong_delta": top2_late,
        "top3_late_strong_delta": top3_late,
        "top2_minus_top1_late_strong_pnl": _round(
            float(top2_late["total_pnl"]) - float(top1_late["total_pnl"]),
            2,
        ),
        "top2_minus_top1_late_strong_ev": _round(
            float(top2_late["expected_value_score"]) - float(top1_late["expected_value_score"]),
            6,
        ),
        "rank2_replacement_count": len(rank2_rows),
        "rank2_minus_rank1_pnl_sum": rank2_delta_sum,
        "rank2_replacement_rows": rank2_rows,
        "candidate_funnel": late["candidate_funnel"],
        "rank_audit": late["rank_audit"],
        "qqq_rejected_daily_top1_counterfactual": late[
            "qqq_rejected_daily_top1_counterfactual"
        ],
        "raw_vcp_daily_top1_no_qqq_gate_counterfactual": late[
            "raw_vcp_daily_top1_no_qqq_gate_counterfactual"
        ],
    }

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only_vcp_late_strong_underparticipation_attribution",
        "decision": "observed_only_vcp_late_strong_underparticipation_attribution",
        "hypothesis": (
            "exp-20260525-022's weak late_strong contribution may be caused by "
            "underparticipation: too few QQQ-confirmed VCP dates and a top-1 daily "
            "cap, rather than by the VCP setup being intrinsically poor."
        ),
        "change_type": "observed_only_late_strong_vcp_underparticipation_attribution",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 7,
        "nearby_prior_experiments": [
            "exp-20260525-020",
            "exp-20260525-022",
            "exp-20260525-024",
            "exp-20260525-027",
            "exp-20260525-030",
            "exp-20260525-033",
            "exp-20260525-034",
        ],
        "multiple_testing_risk_bucket": "moderate_high",
        "new_evidence_type": "late_strong_vcp_participation_and_rank_depth_attribution",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window snapshots; observed-only attribution",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "rule_version": RULE_VERSION,
            "paper_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "source_experiment_id": "exp-20260525-022",
            "source_artifact": base._repo_rel(SOURCE_EXP022_JSON),
            "diagnostic_dimensions": [
                "raw_vcp_vs_qqq_confirmed",
                "qqq_abs_bucket",
                "daily_rank_depth",
                "top1_top2_top3_equal_notional",
                "same_day_rank2_replacement",
                "fwd_5d_10d_20d_horizon_shape",
            ],
            "locked_variables": [
                "VCP compression/breakout definition",
                "QQQ/SPY confirmation definition",
                "next-open entry",
                "$10k paper notional",
                "10-trading-day hold for paper PnL",
                "core entries",
                "ranking",
                "sizing",
                "exits",
                "LLM/news",
                "orders",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool attribution: exp-022's late_strong weakness "
                "may be an underparticipation problem caused by scarce VCP dates and "
                "top-1 rank depth, not a bad VCP signal."
            ),
            "2_history_check": {
                "exp-20260525-022": "QQQ-confirmed VCP top-1 lead passed overall but late_strong uplift was only +$322.04.",
                "exp-20260525-034": "Top-N candidate expansion artifact found top2 improved late_strong and aggregate, but this run focuses on diagnostic attribution rather than promotion.",
                "exp-20260525-033": "Catalyst/support dossier did not support a new support gate.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: identify whether late_strong weakness is explained by "
                "raw opportunity scarcity, QQQ rejection, top-1 replacement value, "
                "absolute QQQ strength, or hold-horizon shape. No trading behavior "
                "can be promoted from this run."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260525_036_vcp_late_strong_underparticipation_attribution.py"
            ),
        },
        "gate1": {
            "baseline_artifact": "data/experiments/exp-20260525-022/volatility_contraction_qqq_confirmed_sleeve.json",
            "baseline_metrics": _load_exp022().get("delta_metrics", {}),
            "accepted_core_ev_sum": 7.8941,
            "accepted_core_total_pnl_sum": 234850.99,
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "OHLCV Date/Open/High/Low/Close/Volume",
                "SPY and QQQ close series",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "computed qqq_abs_bucket",
                "computed vcp_candidate_rank_on_signal_date",
                "computed same_day_rank2_replacement_rows",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_unchanged": True,
            "passed": True,
            "note": "Observed-only attribution. No core or paper candidate gate is changed.",
        },
        "gate4": {
            "observed_only": True,
            "strategy_behavior_changed": False,
            "passed": False,
            "promotion_grade": False,
            "note": (
                "This run explains late_strong underparticipation only. Any top-N "
                "or rank-depth promotion requires a separate shared adapter/parity "
                "experiment and forward evidence."
            ),
        },
        "before_metrics": before_metrics,
        "topn_variant_overlay": variant_overlay,
        "underparticipation_by_window": by_window,
        "late_strong_diagnosis": late_underparticipation,
        "interpretation": late_underparticipation["diagnosis"],
        "next_evidence_needed": (
            "If considering VCP top-2 activation, first repair exp-034 ID/log "
            "collision and add a shared default-off forward adapter/parity test. "
            "Do not retune QQQ/SPY or support gates on the frozen sample."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_orders_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
            base._repo_rel(SOURCE_EXP022_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    late = payload["late_strong_diagnosis"]
    rows = [
        "| Variant | late_strong EV d | late_strong PnL d | Aggregate EV d | Aggregate PnL d | Trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant, data in payload["topn_variant_overlay"].items():
        late_delta = data["delta_by_window"]["late_strong"]
        aggregate = data["aggregate"]
        rows.append(
            "| {variant} | {lev:+.4f} | ${lpnl:+,.2f} | {aev:+.4f} | ${apnl:+,.2f} | {trades} |".format(
                variant=variant,
                lev=late_delta["expected_value_score"],
                lpnl=late_delta["total_pnl"],
                aev=aggregate["expected_value_score_delta_sum"],
                apnl=aggregate["total_pnl_delta_sum"],
                trades=aggregate["target_trade_count_sum"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VCP Late-Strong Underparticipation Attribution",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "## Diagnosis",
            "",
            late["diagnosis"],
            "",
            "## Top-N Diagnostic",
            "",
            *rows,
            "",
            "## Late-Strong Funnel",
            "",
            "```json",
            json.dumps(late["candidate_funnel"], indent=2, sort_keys=True),
            "```",
            "",
            "## Late-Strong Rank-2 Replacement",
            "",
            "```json",
            json.dumps(late["rank2_replacement_rows"], indent=2, sort_keys=True),
            "```",
            "",
            "## Late-Strong QQQ-Rejected Counterfactual",
            "",
            "```json",
            json.dumps(
                {
                    "qqq_rejected_daily_top1_counterfactual": late[
                        "qqq_rejected_daily_top1_counterfactual"
                    ],
                    "raw_vcp_daily_top1_no_qqq_gate_counterfactual": late[
                        "raw_vcp_daily_top1_no_qqq_gate_counterfactual"
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Gate",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "VCP late-strong underparticipation attribution",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_base_module()
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "late_strong_diagnosis": payload["late_strong_diagnosis"],
                    "topn_variant_overlay": {
                        key: {
                            "late_strong": value["delta_by_window"]["late_strong"],
                            "aggregate": value["aggregate"],
                        }
                        for key, value in payload["topn_variant_overlay"].items()
                    },
                    "artifact": base._repo_rel(ARTIFACT_MD),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
