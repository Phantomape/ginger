"""exp-20260528-002: Kova high-volume weak-close exit shadow replay.

This script tests one closed-trade shadow variable on the accepted
exp-20260526-007 VCP top-2 paper sleeve:

- after entry, if a high-volume weak close loses 21/50-day support and either
  falls below entry or gives back at least 5% from the post-entry close high,
  exit at the next open with sell-side slippage;
- otherwise keep the original source exit and PnL.

No production strategy, backtester, ranking, entry, sizing, universe, LLM/news,
or live order path changes here.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


EXPERIMENTS_DIR = Path(__file__).resolve().parent
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))

from exp_20260526_022_vcp_base_geometry_higher_low_attribution import (  # noqa: E402
    REPO_ROOT,
    SOURCE_EXP007_JSON,
    WINDOWS,
    _audit_open_positions,
    _date10,
    _load_json,
    _load_snapshot,
    _now,
    _num,
    _repo_rel,
    _safe,
    _write_json,
    _write_text,
)


EXPERIMENT_ID = "exp-20260528-002"
STEM = "kova_high_volume_weak_close_exit_shadow_replay"
OUT_JSON_NAME = "exp_20260528_002_kova_high_volume_weak_close_exit_shadow_replay.json"
TRIAL_FAMILY = "kova_defensive_exit_shadow_replay"
CHANGED_VARIABLE = "kova_high_volume_weak_close_exit_shadow_v1"
RULE_VERSION = "kova_high_volume_weak_close_exit_v1"
SOURCE_VARIANT = "rank2_125"

VOLUME_LOOKBACK_DAYS = 50
MIN_VOLUME_LOOKBACK_DAYS = 20
VOLUME_RATIO_MIN = 1.50
CLOSE_LOCATION_MAX = 0.40
SHORT_MA_DAYS = 21
MEDIUM_MA_DAYS = 50
GIVEBACK_FROM_POST_ENTRY_CLOSE_HIGH_PCT = 0.05
EXIT_SLIPPAGE_BPS = 5.0
MIN_TRIGGERED_TRADES = 10
MAX_SINGLE_POSITIVE_DELTA_SHARE = 0.40

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / OUT_JSON_NAME
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_source_rank_profile() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP007_JSON)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} profile result")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} target_trades_by_window")
    return {"source": source, "variant": variant, "target_trades_by_window": trades_by_window}


def _source_trade_rows(source: dict[str, Any]) -> "OrderedDict[str, list[dict[str, Any]]]":
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        out[label] = [
            {**row, "window": label}
            for row in source["target_trades_by_window"].get(label, [])
        ]
    return out


def _row_date(row: dict[str, Any]) -> str:
    return _date10(row.get("Date") if "Date" in row else row.get("date"))


def _field(row: dict[str, Any], name: str) -> float | None:
    value = row.get(name)
    if value is None:
        value = row.get(name.lower())
    return _num(value)


def _load_ohlcv_by_window() -> dict[str, dict[str, list[dict[str, Any]]]]:
    return {
        label: _load_snapshot(cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }


def _find_index(rows: list[dict[str, Any]], target_date: str) -> int | None:
    for idx, row in enumerate(rows):
        if _row_date(row) == target_date:
            return idx
    return None


def _mean(values: list[float]) -> float | None:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _moving_average(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    start = idx - days + 1
    if start < 0:
        return None
    closes = [_field(row, "Close") for row in rows[start : idx + 1]]
    values = [value for value in closes if value is not None and value > 0]
    if len(values) != days:
        return None
    return _mean(values)


def _volume_ratio(rows: list[dict[str, Any]], idx: int) -> tuple[float | None, int]:
    start = max(0, idx - VOLUME_LOOKBACK_DAYS)
    prior_volumes = [
        value
        for row in rows[start:idx]
        for value in [_field(row, "Volume")]
        if value is not None and value > 0
    ]
    if len(prior_volumes) < MIN_VOLUME_LOOKBACK_DAYS:
        return None, len(prior_volumes)
    avg_volume = _mean(prior_volumes)
    volume = _field(rows[idx], "Volume")
    if avg_volume is None or avg_volume <= 0 or volume is None:
        return None, len(prior_volumes)
    return volume / avg_volume, len(prior_volumes)


def _close_location(row: dict[str, Any]) -> float | None:
    high = _field(row, "High")
    low = _field(row, "Low")
    close = _field(row, "Close")
    if high is None or low is None or close is None:
        return None
    if high <= low:
        return 0.5
    return (close - low) / (high - low)


def _support_break_type(close: float, ma21: float | None, ma50: float | None) -> str | None:
    below_21 = ma21 is not None and close < ma21
    below_50 = ma50 is not None and close < ma50
    if below_21 and below_50:
        return "below_21d_and_50d_ma"
    if below_50:
        return "below_50d_ma"
    if below_21:
        return "below_21d_ma"
    return None


def _shadow_trade(
    trade: dict[str, Any],
    ohlcv_by_window: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    window = str(trade.get("window") or "")
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = _date10(trade.get("entry_date"))
    exit_date = _date10(trade.get("exit_date"))
    entry_price = _num(trade.get("entry_price"))
    base_pnl = _num(trade.get("pnl")) or 0.0
    base_notional = _num(trade.get("paper_notional_usd")) or 0.0
    bars = ohlcv_by_window.get(window, {}).get(ticker, [])
    entry_idx = _find_index(bars, entry_date)
    exit_idx = _find_index(bars, exit_date)
    base_pnl_pct = base_pnl / base_notional if base_notional else None
    result = {
        "window": window,
        "ticker": ticker,
        "signal_date": _date10(trade.get("signal_date") or trade.get("date")),
        "entry_date": entry_date,
        "exit_date": exit_date,
        "base_notional": round(base_notional, 4),
        "base_pnl": round(base_pnl, 4),
        "base_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "exit_triggered": False,
        "exit_status": "not_triggered",
        "exit_pnl": 0.0,
        "after_pnl": round(base_pnl, 4),
        "after_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "delta_pnl": 0.0,
    }
    if not bars:
        result["exit_status"] = "missing_ohlcv_rows"
        return result
    if entry_idx is None or exit_idx is None or entry_price is None or entry_price <= 0:
        result["exit_status"] = "missing_entry_or_exit_bar"
        return result
    if exit_idx <= entry_idx + 1:
        result["exit_status"] = "source_exit_too_soon_for_next_open_defensive_exit"
        return result

    post_entry_high_close = entry_price
    saw_actionable_bar = False
    for idx in range(entry_idx + 1, exit_idx):
        row = bars[idx]
        next_row = bars[idx + 1]
        close = _field(row, "Close")
        high = _field(row, "High")
        low = _field(row, "Low")
        next_open = _field(next_row, "Open")
        if close is None or close <= 0 or high is None or low is None or next_open is None:
            continue
        post_entry_high_close = max(post_entry_high_close, close)
        ma21 = _moving_average(bars, idx, SHORT_MA_DAYS)
        ma50 = _moving_average(bars, idx, MEDIUM_MA_DAYS)
        support_break = _support_break_type(close, ma21, ma50)
        vol_ratio, vol_lookback = _volume_ratio(bars, idx)
        close_loc = _close_location(row)
        giveback = (
            1.0 - close / post_entry_high_close
            if post_entry_high_close > 0
            else None
        )
        below_entry = close < entry_price
        material_giveback = (
            giveback is not None
            and giveback >= GIVEBACK_FROM_POST_ENTRY_CLOSE_HIGH_PCT
        )
        if vol_lookback >= MIN_VOLUME_LOOKBACK_DAYS:
            saw_actionable_bar = True
        if (
            support_break is not None
            and vol_ratio is not None
            and vol_ratio >= VOLUME_RATIO_MIN
            and close_loc is not None
            and close_loc <= CLOSE_LOCATION_MAX
            and (below_entry or material_giveback)
        ):
            exit_price = next_open * (1.0 - EXIT_SLIPPAGE_BPS / 10000.0)
            exit_return = exit_price / entry_price - 1.0
            exit_pnl = base_notional * exit_return
            delta_pnl = exit_pnl - base_pnl
            result.update(
                {
                    "exit_triggered": True,
                    "exit_status": "high_volume_weak_close_support_break_exit_next_open",
                    "trigger_date": _row_date(row),
                    "exit_fill_date": _row_date(next_row),
                    "support_break_type": support_break,
                    "trigger_close": round(close, 4),
                    "trigger_close_vs_entry_pct": round(close / entry_price - 1.0, 6),
                    "post_entry_high_close": round(post_entry_high_close, 4),
                    "giveback_from_post_entry_close_high_pct": round(giveback or 0.0, 6),
                    "volume_ratio_50d": round(vol_ratio, 6),
                    "volume_lookback_days": vol_lookback,
                    "close_location": round(close_loc, 6),
                    "ma21": round(ma21, 4) if ma21 is not None else None,
                    "ma50": round(ma50, 4) if ma50 is not None else None,
                    "exit_raw_open": round(next_open, 4),
                    "exit_price": round(exit_price, 4),
                    "exit_return": round(exit_return, 6),
                    "exit_pnl": round(exit_pnl, 4),
                    "after_pnl": round(exit_pnl, 4),
                    "after_pnl_pct": round(exit_pnl / base_notional, 6)
                    if base_notional
                    else None,
                    "delta_pnl": round(delta_pnl, 4),
                }
            )
            return result
    if not saw_actionable_bar:
        result["exit_status"] = "insufficient_volume_lookback_for_exit_rule"
    return result


def _metric_summary(rows: list[dict[str, Any]], pnl_key: str) -> dict[str, Any]:
    pnls = [float(row.get(pnl_key) or 0.0) for row in rows]
    notionals = [float(row.get("base_notional") or 0.0) for row in rows]
    pct_returns = [
        pnl / notional
        for pnl, notional in zip(pnls, notionals)
        if notional and math.isfinite(pnl / notional)
    ]
    total_pnl = sum(pnls)
    total_notional = sum(notionals)
    ret_pct = total_pnl / total_notional if total_notional else 0.0
    if len(pct_returns) >= 2 and pstdev(pct_returns) > 0:
        trade_sharpe_proxy = mean(pct_returns) / pstdev(pct_returns) * math.sqrt(len(pct_returns))
    else:
        trade_sharpe_proxy = 0.0
    return {
        "trade_count": len(rows),
        "total_pnl": round(total_pnl, 4),
        "total_notional": round(total_notional, 4),
        "return_on_notional": round(ret_pct, 6),
        "avg_pnl": round(total_pnl / len(rows), 4) if rows else 0.0,
        "win_rate": round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 6) if pnls else 0.0,
        "trade_sharpe_proxy": round(trade_sharpe_proxy, 6),
        "expected_value_proxy": round(ret_pct * trade_sharpe_proxy, 6),
    }


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
    deltas = [float(row.get("delta_pnl") or 0.0) for row in triggered_rows]
    positive_deltas = [delta for delta in deltas if delta > 0]
    positive_sum = sum(positive_deltas)
    max_single_positive_delta_share = (
        max(positive_deltas) / positive_sum
        if positive_sum > 0 and positive_deltas
        else None
    )
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
            "triggered_count": len(triggered_rows),
            "triggered_rate": round(len(triggered_rows) / len(rows), 6) if rows else 0.0,
            "status_counts": dict(sorted(Counter(row["exit_status"] for row in rows).items())),
            "total_exit_delta_pnl": round(sum(deltas), 4),
            "avg_exit_delta_pnl": round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
            "beneficial_exit_count": sum(1 for delta in deltas if delta > 0),
            "harmful_exit_count": sum(1 for delta in deltas if delta < 0),
            "max_single_positive_delta_share": round(max_single_positive_delta_share, 6)
            if max_single_positive_delta_share is not None
            else None,
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
    concentration_ok = (
        exit_summary["max_single_positive_delta_share"] is not None
        and exit_summary["max_single_positive_delta_share"] < MAX_SINGLE_POSITIVE_DELTA_SHARE
    )
    passed = (
        pnl_delta > 0
        and ev_proxy_delta > 0
        and not windows_regressed
        and exit_summary["triggered_count"] >= MIN_TRIGGERED_TRADES
        and concentration_ok
    )
    evidence = {
        "aggregate_total_pnl_delta": pnl_delta,
        "expected_value_proxy_delta": ev_proxy_delta,
        "triggered_count": exit_summary["triggered_count"],
        "triggered_count_min": MIN_TRIGGERED_TRADES,
        "windows_regressed": windows_regressed,
        "max_single_positive_delta_share": exit_summary["max_single_positive_delta_share"],
        "max_single_positive_delta_share_max": MAX_SINGLE_POSITIVE_DELTA_SHARE,
        "shadow_gate_passed": passed,
    }
    if passed:
        return (
            "observed_only_promising_kova_high_volume_weak_close_exit_needs_full_replay",
            "observed_only",
            evidence,
            (
                "The Kova high-volume weak-close support-break exit improved "
                "closed-trade EV proxy and PnL without window PnL regression. "
                "Treat it as a candidate for a full shared lifecycle replay, "
                "not as a production change."
            ),
        )
    if pnl_delta <= 0 or ev_proxy_delta <= 0:
        reason = "aggregate PnL or EV proxy did not improve"
    elif windows_regressed:
        reason = "one or more canonical windows regressed"
    elif exit_summary["triggered_count"] < MIN_TRIGGERED_TRADES:
        reason = "sample too small"
    else:
        reason = "positive delta concentration failed"
    return (
        "rejected_kova_high_volume_weak_close_exit_shadow_replay",
        "rejected",
        evidence,
        (
            "The Kova high-volume weak-close support-break exit failed Gate 4 "
            f"because {reason}. No Kova defensive-exit rule should be promoted "
            "from this shadow replay."
        ),
    )


def _build_payload() -> dict[str, Any]:
    created_at = _now()
    source = _load_source_rank_profile()
    trades_by_window = _source_trade_rows(source)
    trades = [row for rows in trades_by_window.values() for row in rows]
    ohlcv_by_window = _load_ohlcv_by_window()
    shadow_rows = [_shadow_trade(trade, ohlcv_by_window) for trade in trades]
    summary = _summaries(shadow_rows)
    decision, status, evidence, summary_text = _decision(summary)
    open_positions_audit = _audit_open_positions()
    source_variant = source["variant"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": created_at,
        "status": status,
        "registry_lane": "alpha_discovery",
        "lane": "alpha_discovery",
        "decision": decision,
        "summary": summary_text,
        "alpha_hypothesis": (
            "Kova defensive sell signals after VCP entry, defined as high-volume "
            "weak closes that break or lose short/medium moving-average support, "
            "may cut failed accepted VCP top-2 paper trades without truncating "
            "valid breakouts."
        ),
        "change_type": "exit_shadow_replay",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "parameters": {
            "volume_lookback_days": VOLUME_LOOKBACK_DAYS,
            "min_volume_lookback_days": MIN_VOLUME_LOOKBACK_DAYS,
            "volume_ratio_min": VOLUME_RATIO_MIN,
            "close_location_max": CLOSE_LOCATION_MAX,
            "short_ma_days": SHORT_MA_DAYS,
            "medium_ma_days": MEDIUM_MA_DAYS,
            "giveback_from_post_entry_close_high_pct": GIVEBACK_FROM_POST_ENTRY_CLOSE_HIGH_PCT,
            "support_break": "close below 21d or 50d moving average",
            "confirmation": "close below entry or >=5pct giveback from post-entry close high",
            "fill": "next open after trigger close",
            "exit_slippage_bps": EXIT_SLIPPAGE_BPS,
        },
        "acceptance_standard": (
            "Accept only as observed candidate if aggregate closed-trade PnL and "
            "EV proxy both improve, no canonical window PnL regresses, at least "
            "10 trades trigger, and max single positive delta share stays below "
            "40%. Strategy promotion would still require a full shared lifecycle "
            "replay."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Kova high-volume weak-close support breaks may identify failed "
                "VCP entries before the fixed 10-trading-day paper exit."
            ),
            "1_category": "exit",
            "1_playbook_alignment": (
                "This follows the playbook's caution on exits: shadow attribution "
                "first, no production or backtester lifecycle change."
            ),
            "2_history_check": {
                "exp-20260526-008": "Post-entry pivot-failure attribution was not actionable.",
                "exp-20260527-016": "Entry-day-low stop shadow replay was rejected.",
                "exp-20260527-910": "Fixed 7.5pct max-loss stop shadow replay was rejected.",
                "exp-20260526-007": "Accepted VCP top-2 rank-notional paper sleeve is the source population.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Closed-trade shadow: aggregate PnL and EV proxy improve, zero "
                "window PnL regression, triggered_count >=10, concentration <40%."
            ),
            "5_reproducibility": "Script writes JSON, markdown, ticket, log, and JSONL row.",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp007 source sleeve",
            "paper_exit": "10 trading days after signal from exp007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
            "strategy_replacement_tested": False,
            "shadow_replay_only": True,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
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
            "required_ohlcv_fields": ["Date", "Open", "High", "Low", "Close", "Volume"],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_trade_count": len(trades),
            "triggered_exit_count": summary["exit"]["triggered_count"],
            "core_survival_changed": False,
            "note": "No filter is added; this only shadows a defensive exit on existing source trades.",
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
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260528_002_kova_high_volume_weak_close_exit_shadow_replay.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "why_not_other_changes": (
            "Did not alter VCP entries, rank-notional profile, ranking, sizing, "
            "universe, LLM/news, backtester, run.py, or live/default orders."
        ),
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
    lines = [
        f"# {EXPERIMENT_ID} Kova High-Volume Weak-Close Exit Shadow Replay",
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
        f"- Triggered exits: `{payload['exit_metrics']['triggered_count']}`.",
        f"- Beneficial exits: `{payload['exit_metrics']['beneficial_exit_count']}`.",
        f"- Harmful exits: `{payload['exit_metrics']['harmful_exit_count']}`.",
        f"- Max single positive delta share: `{payload['exit_metrics']['max_single_positive_delta_share']}`.",
        "",
        "## Windows",
        "",
        *_window_table(payload),
        "",
        "## Gate 4",
        "",
        "```json",
        json.dumps(payload["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Repro",
        "",
        "```powershell",
        payload["repro_command"],
        "```",
        "",
    ]
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    updated = False
    for row in experiments:
        if not isinstance(row, dict):
            continue
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": row.get("owner") or "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
        updated = True
        break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "log_file": _repo_rel(LOG_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _existing_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    try:
        return _load_json(TICKET_JSON)
    except json.JSONDecodeError:
        return {}


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    existing = _existing_ticket()
    ticket_payload = {
        "experiment_id": payload["experiment_id"],
        "experiment_uid": existing.get("experiment_uid"),
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["registry_lane"],
        "owner": existing.get("owner") or "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": "kova_sell_side_lifecycle",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 3),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_vcp_trade_exit_shadow_replay",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260528_002_kova_high_volume_weak_close_exit_shadow_replay.py")),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
        ],
        "must_not_touch": [
            "quant/backtester.py",
            "quant/run.py",
            "operator_inputs/open_positions.json",
        ],
        "locked_variables": [
            "kova_high_volume_weak_close_exit_shadow_v1",
            "VCP top-2 entries",
            "VCP rank-notional profile",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
        "prediction": existing.get("prediction"),
        "created_at": existing.get("created_at", payload["created_at"]),
        "claimed_at": existing.get("claimed_at"),
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": payload["artifacts"]["markdown"],
            "json": payload["artifacts"]["json"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(TICKET_JSON, ticket_payload)
    _write_json(DOCS_TICKET_JSON, ticket_payload)
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status": payload["status"],
                "aggregate": {
                    "before": payload["before_metrics"],
                    "after": payload["after_metrics"],
                    "delta": payload["delta_metrics"],
                },
                "exit": payload["exit_metrics"],
                "gate4": payload["gate4"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
