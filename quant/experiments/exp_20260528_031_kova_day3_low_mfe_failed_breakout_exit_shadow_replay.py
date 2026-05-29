"""exp-20260528-031: Kova day-3 low-MFE failed-breakout exit shadow replay.

This follows the Kova sell-side lifecycle taxonomy from exp-20260528-014.
That taxonomy found a populated negative `failed_breakout_low_mfe` bucket, but
the taxonomy label itself used full 10-day outcomes and could not be promoted.

This script tests one ex-ante shadow exit trigger on the accepted
exp-20260526-007 QQQ-confirmed VCP top-2 paper trades:

- on the third trading day since entry, including the entry day, if the trade
  has never reached +2% intraday MFE, closes at or below entry, and has already
  touched -4% intraday MAE, exit at the next open with sell-side slippage;
- otherwise keep the original 10-trading-day paper exit.

No production strategy, backtester, ranking, entry, sizing, universe, LLM/news,
or live order path changes here. No JavaScript was used.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260528_002_kova_high_volume_weak_close_exit_shadow_replay import (  # noqa: E402
    REPO_ROOT,
    SOURCE_VARIANT,
    _audit_open_positions,
    _field,
    _find_index,
    _load_ohlcv_by_window,
    _load_source_rank_profile,
    _metric_summary,
    _num,
    _repo_rel,
    _row_date,
    _safe,
    _source_trade_rows,
    _write_json,
)
from exp_20260526_022_vcp_base_geometry_higher_low_attribution import WINDOWS  # noqa: E402


EXPERIMENT_ID = "exp-20260528-031"
STEM = "kova_day3_low_mfe_failed_breakout_exit_shadow_replay"
OUT_JSON_NAME = f"{STEM}.json"
TRIAL_FAMILY = "kova_failed_breakout_lifecycle_shadow_replay"
CHANGED_VARIABLE = "kova_day3_low_mfe_failed_breakout_exit_v1"
RULE_VERSION = "kova_day3_low_mfe_failed_breakout_exit_v1"

SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260526-007"
    / "vcp_rank_notional_profile.json"
)
TAXONOMY_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260528-014"
    / "kova_sell_side_lifecycle_taxonomy.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / OUT_JSON_NAME
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

CHECK_DAY_COUNT = 3
MAX_HIGH_RETURN_THROUGH_CHECK = 0.02
MAX_CLOSE_RETURN_AT_CHECK = 0.0
MIN_LOW_RETURN_THROUGH_CHECK = -0.04
EXIT_SLIPPAGE_BPS = 5.0
MIN_TRIGGERED_TRADES = 10
MAX_SINGLE_POSITIVE_DELTA_SHARE = 0.40
MIN_FAILED_LOW_MFE_LABEL_SHARE = 0.45
ANTI_JS = "No JavaScript was used."

BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "baseline_source": "docs/backtesting.md accepted aggregate core stack",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(line + "\n", encoding="utf-8")
        return

    found = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for existing in handle:
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                found = True
                break

    if not found:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        return

    rows: list[str] = []
    replaced = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for existing in handle:
            if not existing.strip():
                continue
            text = existing.rstrip("\n")
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                rows.append(text)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(text)
    tmp_path = path.with_name(f"{path.name}.{EXPERIMENT_ID}.tmp")
    tmp_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _load_taxonomy_rows() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    if not TAXONOMY_ARTIFACT.exists():
        return {}
    payload = json.loads(TAXONOMY_ARTIFACT.read_text(encoding="utf-8"))
    out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in payload.get("classified_trades", []):
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("window") or ""),
            str(row.get("ticker") or "").upper(),
            str(row.get("signal_date") or "")[:10],
            str(row.get("entry_date") or "")[:10],
        )
        out[key] = row
    return out


def _taxonomy_for(
    trade: dict[str, Any],
    taxonomy_rows: dict[tuple[str, str, str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    key = (
        str(trade.get("window") or ""),
        str(trade.get("ticker") or "").upper(),
        str(trade.get("signal_date") or trade.get("date") or "")[:10],
        str(trade.get("entry_date") or "")[:10],
    )
    return taxonomy_rows.get(key)


def _positive_delta_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        delta = float(row.get("delta_pnl") or 0.0)
        if delta > 0:
            by_ticker[str(row.get("ticker") or "")] += delta
    total = sum(by_ticker.values())
    ranked = [
        {"ticker": ticker, "positive_delta_pnl": value, "share": value / total if total > 0 else None}
        for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
    ]
    return {
        "positive_delta_total": round(total, 4),
        "top_ticker": ranked[0]["ticker"] if ranked else None,
        "top_ticker_positive_delta_share": ranked[0]["share"] if ranked else None,
        "by_ticker": ranked,
    }


def _shadow_trade(
    trade: dict[str, Any],
    ohlcv_by_window: dict[str, dict[str, list[dict[str, Any]]]],
    taxonomy_rows: dict[tuple[str, str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    window = str(trade.get("window") or "")
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    entry_date = str(trade.get("entry_date") or "")[:10]
    exit_date = str(trade.get("exit_date") or "")[:10]
    entry_price = _num(trade.get("entry_price"))
    base_pnl = _num(trade.get("pnl")) or 0.0
    base_notional = _num(trade.get("paper_notional_usd")) or 0.0
    base_pnl_pct = base_pnl / base_notional if base_notional else None
    taxonomy = _taxonomy_for(trade, taxonomy_rows) or {}

    result: dict[str, Any] = {
        "window": window,
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "source_exit_date": exit_date,
        "vcp_candidate_rank_on_signal_date": trade.get("vcp_candidate_rank_on_signal_date"),
        "base_notional": round(base_notional, 4),
        "base_pnl": round(base_pnl, 4),
        "base_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "taxonomy_primary_sell_side_bucket": taxonomy.get("primary_sell_side_bucket"),
        "taxonomy_sell_side_labels": taxonomy.get("sell_side_labels") or [],
        "exit_triggered": False,
        "exit_status": "not_triggered",
        "after_pnl": round(base_pnl, 4),
        "after_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "delta_pnl": 0.0,
        "trigger_date": None,
        "exit_fill_date": None,
        "observed_trading_days": 0,
        "max_high_return_through_check": None,
        "close_return_at_check": None,
        "min_low_return_through_check": None,
    }

    bars = ohlcv_by_window.get(window, {}).get(ticker, [])
    entry_idx = _find_index(bars, entry_date)
    source_exit_idx = _find_index(bars, exit_date)
    if not bars:
        result["exit_status"] = "missing_ohlcv_rows"
        return result
    if entry_idx is None or source_exit_idx is None or entry_price is None or entry_price <= 0:
        result["exit_status"] = "missing_entry_or_exit_bar"
        return result

    trigger_idx = entry_idx + CHECK_DAY_COUNT - 1
    fill_idx = trigger_idx + 1
    if fill_idx > source_exit_idx:
        result["exit_status"] = "source_exit_too_soon_for_day3_exit"
        return result
    if trigger_idx >= len(bars) or fill_idx >= len(bars):
        result["exit_status"] = "missing_day3_or_next_open_bar"
        return result

    observed = bars[entry_idx : trigger_idx + 1]
    highs = [value for row in observed for value in [_field(row, "High")] if value is not None]
    lows = [value for row in observed for value in [_field(row, "Low")] if value is not None]
    trigger_close = _field(bars[trigger_idx], "Close")
    next_open = _field(bars[fill_idx], "Open")
    if not highs or not lows or trigger_close is None or next_open is None:
        result["exit_status"] = "missing_day3_price_fields"
        return result

    max_high_return = max(highs) / entry_price - 1.0
    min_low_return = min(lows) / entry_price - 1.0
    close_return = trigger_close / entry_price - 1.0
    result.update(
        {
            "trigger_date": _row_date(bars[trigger_idx]),
            "exit_fill_date": _row_date(bars[fill_idx]),
            "observed_trading_days": CHECK_DAY_COUNT,
            "max_high_return_through_check": round(max_high_return, 6),
            "close_return_at_check": round(close_return, 6),
            "min_low_return_through_check": round(min_low_return, 6),
            "trigger_close": round(trigger_close, 4),
            "exit_raw_open": round(next_open, 4),
        }
    )

    trigger = (
        max_high_return <= MAX_HIGH_RETURN_THROUGH_CHECK
        and close_return <= MAX_CLOSE_RETURN_AT_CHECK
        and min_low_return <= MIN_LOW_RETURN_THROUGH_CHECK
    )
    if not trigger:
        return result

    exit_price = next_open * (1.0 - EXIT_SLIPPAGE_BPS / 10000.0)
    exit_return = exit_price / entry_price - 1.0
    exit_pnl = base_notional * exit_return
    delta_pnl = exit_pnl - base_pnl
    result.update(
        {
            "exit_triggered": True,
            "exit_status": "day3_low_mfe_failed_breakout_exit_next_open",
            "exit_price": round(exit_price, 4),
            "exit_return": round(exit_return, 6),
            "exit_pnl": round(exit_pnl, 4),
            "after_pnl": round(exit_pnl, 4),
            "after_pnl_pct": round(exit_pnl / base_notional, 6) if base_notional else None,
            "delta_pnl": round(delta_pnl, 4),
        }
    )
    return result


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label in WINDOWS:
        window_rows = [row for row in rows if row.get("window") == label]
        before = _metric_summary(window_rows, "base_pnl")
        after = _metric_summary(window_rows, "after_pnl")
        by_window[label] = {
            "before": before,
            "after": after,
            "delta": {
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 4),
                "expected_value_proxy": round(
                    after["expected_value_proxy"] - before["expected_value_proxy"],
                    6,
                ),
                "return_on_notional": round(
                    after["return_on_notional"] - before["return_on_notional"],
                    6,
                ),
            },
            "triggered_count": sum(1 for row in window_rows if row.get("exit_triggered")),
        }
    before_all = _metric_summary(rows, "base_pnl")
    after_all = _metric_summary(rows, "after_pnl")
    triggered_rows = [row for row in rows if row.get("exit_triggered")]
    delta_pnls = [float(row.get("delta_pnl") or 0.0) for row in triggered_rows]
    label_counts = Counter(
        str(row.get("taxonomy_primary_sell_side_bucket") or "missing_taxonomy")
        for row in triggered_rows
    )
    target_hits = sum(
        1
        for row in triggered_rows
        if "failed_breakout_low_mfe" in (row.get("taxonomy_sell_side_labels") or [])
        or row.get("taxonomy_primary_sell_side_bucket") == "failed_breakout_low_mfe"
    )
    triggered_count = len(triggered_rows)
    concentration = _positive_delta_concentration(triggered_rows)
    return {
        "aggregate": {
            "before": before_all,
            "after": after_all,
            "delta": {
                "total_pnl": round(after_all["total_pnl"] - before_all["total_pnl"], 4),
                "total_pnl_delta_pct": round(
                    (after_all["total_pnl"] - before_all["total_pnl"])
                    / abs(before_all["total_pnl"]),
                    6,
                )
                if before_all["total_pnl"]
                else None,
                "expected_value_proxy": round(
                    after_all["expected_value_proxy"] - before_all["expected_value_proxy"],
                    6,
                ),
                "return_on_notional": round(
                    after_all["return_on_notional"] - before_all["return_on_notional"],
                    6,
                ),
            },
        },
        "by_window": by_window,
        "exit": {
            "triggered_count": triggered_count,
            "triggered_rate": round(triggered_count / len(rows), 6) if rows else 0.0,
            "status_counts": dict(sorted(Counter(row["exit_status"] for row in rows).items())),
            "total_exit_delta_pnl": round(sum(delta_pnls), 4),
            "avg_exit_delta_pnl": round(sum(delta_pnls) / triggered_count, 4)
            if triggered_count
            else 0.0,
            "beneficial_exit_count": sum(1 for value in delta_pnls if value > 0),
            "harmful_exit_count": sum(1 for value in delta_pnls if value < 0),
            "taxonomy_primary_bucket_counts": dict(sorted(label_counts.items())),
            "failed_low_mfe_label_hits": target_hits,
            "failed_low_mfe_label_share": round(target_hits / triggered_count, 6)
            if triggered_count
            else None,
            "positive_delta_concentration": concentration,
        },
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str, dict[str, Any], str]:
    aggregate = summary["aggregate"]
    exit_summary = summary["exit"]
    pnl_delta = aggregate["delta"]["total_pnl"]
    ev_proxy_delta = aggregate["delta"]["expected_value_proxy"]
    windows_regressed = [
        window
        for window, row in summary["by_window"].items()
        if row["delta"]["total_pnl"] < -1e-6
    ]
    top_share = exit_summary["positive_delta_concentration"]["top_ticker_positive_delta_share"]
    concentration_ok = top_share is not None and top_share <= MAX_SINGLE_POSITIVE_DELTA_SHARE
    label_share = exit_summary["failed_low_mfe_label_share"]
    label_precision_ok = label_share is not None and label_share >= MIN_FAILED_LOW_MFE_LABEL_SHARE
    passed = (
        pnl_delta > 0
        and ev_proxy_delta > 0
        and not windows_regressed
        and exit_summary["triggered_count"] >= MIN_TRIGGERED_TRADES
        and concentration_ok
        and label_precision_ok
    )
    evidence = {
        "aggregate_total_pnl_delta": pnl_delta,
        "expected_value_proxy_delta": ev_proxy_delta,
        "triggered_count": exit_summary["triggered_count"],
        "triggered_count_min": MIN_TRIGGERED_TRADES,
        "windows_regressed": windows_regressed,
        "top_ticker_positive_delta_share": top_share,
        "top_ticker_positive_delta_share_max": MAX_SINGLE_POSITIVE_DELTA_SHARE,
        "failed_low_mfe_label_share": label_share,
        "failed_low_mfe_label_share_min": MIN_FAILED_LOW_MFE_LABEL_SHARE,
        "shadow_gate_passed": passed,
    }
    if passed:
        return (
            "observed_only_promising_kova_day3_low_mfe_exit_needs_full_lifecycle_replay",
            "observed_only",
            evidence,
            (
                "The day-3 low-MFE failed-breakout exit improved aggregate "
                "closed-trade PnL and EV proxy without window regression and "
                "mostly hit the taxonomy target bucket. Treat it as a candidate "
                "for a full shared lifecycle replay, not as a production change."
            ),
        )
    if pnl_delta <= 0 or ev_proxy_delta <= 0:
        reason = "aggregate PnL or EV proxy did not improve"
    elif windows_regressed:
        reason = "one or more canonical windows regressed"
    elif exit_summary["triggered_count"] < MIN_TRIGGERED_TRADES:
        reason = "triggered sample was too small"
    elif not label_precision_ok:
        reason = "ex-ante trigger did not map cleanly to the failed-low-MFE taxonomy bucket"
    else:
        reason = "positive delta concentration failed"
    return (
        "rejected_kova_day3_low_mfe_failed_breakout_exit_shadow_replay",
        "rejected",
        evidence,
        (
            "The day-3 low-MFE failed-breakout exit failed Gate 4 because "
            f"{reason}. No Kova failed-breakout exit rule should be promoted "
            "from this shadow replay."
        ),
    )


def _build_payload() -> dict[str, Any]:
    created_at = _utc_now()
    source = _load_source_rank_profile()
    trades_by_window = _source_trade_rows(source)
    trades = [row for rows in trades_by_window.values() for row in rows]
    ohlcv_by_window = _load_ohlcv_by_window()
    taxonomy_rows = _load_taxonomy_rows()
    shadow_rows = [_shadow_trade(trade, ohlcv_by_window, taxonomy_rows) for trade in trades]
    summary = _summaries(shadow_rows)
    decision, status, evidence, summary_text = _decision(summary)
    open_positions_audit = _audit_open_positions()
    source_variant = source["variant"]
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(SOURCE_ARTIFACT),
        _repo_rel(TAXONOMY_ARTIFACT),
        _repo_rel(OUT_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOCS_TICKET_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": created_at,
        "status": status,
        "registry_lane": "alpha_discovery",
        "lane": "alpha_discovery",
        "decision": decision,
        "summary": summary_text,
        "hypothesis": (
            "Kova failed-breakout VCP losses can be cut by an ex-ante day-3 "
            "low-MFE trigger that exits trades showing no upside progress and "
            "material early adverse excursion."
        ),
        "change_summary": (
            "Shadow-replays one Kova sell-side lifecycle rule on the accepted "
            "exp-20260526-007 VCP top-2 paper trades: day-3 low-MFE failed "
            "breakouts exit at the next open; all other source exits remain fixed."
        ),
        "change_type": "exit_shadow_replay",
        "mechanism_family": "kova_canslim_sell_side_lifecycle",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "prior_trial_count": 6,
        "nearby_prior_experiments": [
            "exp-20260526-008",
            "exp-20260527-016",
            "exp-20260527-910",
            "exp-20260528-002",
            "exp-20260528-014",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "ex_ante_lifecycle_shadow_replay_from_observed_negative_taxonomy_bucket",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "source_variant": SOURCE_VARIANT,
            "taxonomy_artifact": _repo_rel(TAXONOMY_ARTIFACT),
            "check_day_count_including_entry_day": CHECK_DAY_COUNT,
            "max_high_return_through_check": MAX_HIGH_RETURN_THROUGH_CHECK,
            "max_close_return_at_check": MAX_CLOSE_RETURN_AT_CHECK,
            "min_low_return_through_check": MIN_LOW_RETURN_THROUGH_CHECK,
            "fill": "next open after trigger day close",
            "exit_slippage_bps": EXIT_SLIPPAGE_BPS,
            "min_triggered_trades": MIN_TRIGGERED_TRADES,
            "max_single_positive_delta_share": MAX_SINGLE_POSITIVE_DELTA_SHARE,
            "min_failed_low_mfe_label_share": MIN_FAILED_LOW_MFE_LABEL_SHARE,
            "anti_js": ANTI_JS,
        },
        "date_range": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Exit/lifecycle: Kova day-3 failed-breakout behavior may cut "
                "VCP top-2 paper losses before the fixed 10-day hold."
            ),
            "1_playbook_alignment": (
                "Uses Kova docs' recommended next work: convert the "
                "failed_breakout_low_mfe taxonomy candidate into an ex-ante "
                "shadow replay, not another threshold gate."
            ),
            "2_history_check": (
                "Entry-day-low stop, fixed max-loss stop, high-volume weak-close "
                "exit, and confirmation pyramid were rejected. exp-20260528-014 "
                "only nominated the failed-low-MFE lifecycle bucket."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Aggregate PnL and EV proxy must improve, no canonical window "
                "may regress, at least 10 exits must trigger, positive delta "
                "must not be concentrated, and the trigger must mostly hit the "
                "failed-low-MFE taxonomy bucket."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260528_031_kova_day3_low_mfe_failed_breakout_exit_shadow_replay.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_ARTIFACT),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp-20260526-007 source sleeve",
            "paper_exit": "10 trading days after signal from exp-20260526-007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
            "shadow_replay_only": True,
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "baseline_result_file": _repo_rel(SOURCE_ARTIFACT),
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get("expected_value_score_delta"),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": len(trades),
                "target_trade_summary": source_variant.get("target_trade_summary"),
            },
            "core_logic_changed": False,
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
            "required_trade_fields": [
                "ticker",
                "entry_date",
                "entry_price",
                "exit_date",
                "paper_notional_usd",
                "pnl",
            ],
            "required_ohlcv_fields": ["Date", "Open", "High", "Low", "Close"],
            "taxonomy_join_coverage": {
                "classified_rows_available": len(taxonomy_rows),
                "source_trades": len(trades),
                "joined_rows": sum(
                    1 for row in shadow_rows if row.get("taxonomy_primary_sell_side_bucket")
                ),
            },
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_trade_count": len(trades),
            "triggered_exit_count": summary["exit"]["triggered_count"],
            "core_survival_changed": False,
            "note": "No entry filter is added; this only shadows a defensive exit on existing source trades.",
        },
        "gate4": {
            "passed": evidence["shadow_gate_passed"],
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": "Closed-trade shadow replay only; no production strategy rule changed.",
            "decision_evidence": evidence,
        },
        "before_metrics": summary["aggregate"]["before"],
        "after_metrics": summary["aggregate"]["after"],
        "delta_metrics": summary["aggregate"]["delta"],
        "window_metrics": summary["by_window"],
        "exit_metrics": summary["exit"],
        "shadow_rows": shadow_rows,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "shadow_replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "expected_value_score_delta": 0.0,
        "rejection_reason": summary_text,
        "next_retry_requires": [
            "new_forward_vcp_rows_or_a_less_leaky_lifecycle_field",
            "full_shared_lifecycle_replay_with_slot_heat_and_replacement_value_accounting",
            "evidence_that_early_low_mfe_exit_does_not_cut_delayed_winners",
        ],
        "related_files": related_files,
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260528_031_kova_day3_low_mfe_failed_breakout_exit_shadow_replay.py"
        ),
        "why_not_other_changes": (
            "Did not alter VCP entries, rank-notional profile, ranking, sizing, "
            "universe, LLM/news, backtester, run.py, or live/default orders."
        ),
        "anti_js": ANTI_JS,
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | triggered | before pnl | after pnl | delta pnl | delta EV proxy |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for window, row in payload["window_metrics"].items():
        lines.append(
            "| {window} | {triggered} | {before} | {after} | {delta} | {ev_delta} |".format(
                window=window,
                triggered=row["triggered_count"],
                before=row["before"]["total_pnl"],
                after=row["after"]["total_pnl"],
                delta=row["delta"]["total_pnl"],
                ev_delta=row["delta"]["expected_value_proxy"],
            )
        )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    exit_metrics = payload["exit_metrics"]
    concentration = exit_metrics["positive_delta_concentration"]
    lines = [
        f"# {EXPERIMENT_ID} Kova Day-3 Low-MFE Failed-Breakout Exit Shadow Replay",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Aggregate",
        "",
        f"- Before PnL: `{payload['before_metrics']['total_pnl']}`.",
        f"- After PnL: `{payload['after_metrics']['total_pnl']}`.",
        f"- Delta PnL: `{payload['delta_metrics']['total_pnl']}`.",
        f"- Delta EV proxy: `{payload['delta_metrics']['expected_value_proxy']}`.",
        f"- Triggered exits: `{exit_metrics['triggered_count']}`.",
        f"- Beneficial exits: `{exit_metrics['beneficial_exit_count']}`.",
        f"- Harmful exits: `{exit_metrics['harmful_exit_count']}`.",
        f"- Failed-low-MFE label share: `{exit_metrics['failed_low_mfe_label_share']}`.",
        f"- Top positive delta ticker share: `{concentration['top_ticker_positive_delta_share']}`.",
        "",
        "## Window Metrics",
        "",
        *_window_table(payload),
        "",
        "## Trigger Taxonomy Buckets",
        "",
        "| taxonomy primary bucket | triggered trades |",
        "|---|---:|",
    ]
    for bucket, count in exit_metrics["taxonomy_primary_bucket_counts"].items():
        lines.append(f"| {bucket} | {count} |")
    lines.extend(
        [
            "",
            "## Related Files",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in payload["related_files"])
    lines.append("")
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "owner": ticket["owner"],
        "status": payload["status"],
        "ticket_file": _repo_rel(TICKET_JSON),
        "updated_at": payload["timestamp"],
    }
    replaced = False
    for idx, item in enumerate(experiments):
        if item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = row
            replaced = True
            break
    if not replaced:
        experiments.append(row)
    registry["updated_at"] = payload["timestamp"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "artifact_file": _repo_rel(OUT_JSON),
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "owner": "codex-kova-lifecycle",
        "result_file": _repo_rel(LOG_JSON),
        "single_causal_variable": CHANGED_VARIABLE,
        "status": payload["status"],
        "updated_at": payload["timestamp"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_json(DOCS_TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload, ticket)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = _build_payload()
    if not args.no_persist:
        _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "delta_metrics": payload["delta_metrics"],
                "exit_metrics": payload["exit_metrics"],
                "output": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
