"""exp-20260527-910: Kova fixed maximum-loss stop shadow replay.

Kova-style loss cutting commonly uses a fixed maximum loss around 7-8% from
entry. This script tests one closed-trade shadow variable on the accepted
exp-20260526-007 VCP top-2 paper sleeve:

- If daily low touches 7.5% below entry before the source exit, exit at the
  stop level, or at the day's open if price gaps below the stop.
- Otherwise keep the original source exit and PnL.

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


EXPERIMENT_ID = "exp-20260527-910"
STEM = "kova_max_loss_stop_shadow_replay"
OUT_JSON_NAME = "exp_20260527_910_kova_max_loss_stop_shadow_replay.json"
TRIAL_FAMILY = "kova_fixed_max_loss_stop_shadow_replay"
CHANGED_VARIABLE = "kova_max_loss_stop_7_5pct_shadow_v1"
RULE_VERSION = "kova_entry_minus_7_5pct_stop_v1"
SOURCE_VARIANT = "rank2_125"

STOP_LOSS_PCT = 0.075
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
    path.parent.mkdir(parents=True, exist_ok=True)
    found = False
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for existing in handle:
                if experiment_id not in existing:
                    continue
                try:
                    row = json.loads(existing)
                except json.JSONDecodeError:
                    continue
                if row.get("experiment_id") == experiment_id:
                    found = True
                    break
    if not found:
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(line + "\n")
        return
    temp_path = path.with_name(path.name + f".{EXPERIMENT_ID}.tmp")
    with path.open("r", encoding="utf-8", errors="replace") as src, temp_path.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        replaced = False
        for existing in src:
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                dst.write(existing.rstrip("\n") + "\n")
                continue
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    dst.write(line + "\n")
                    replaced = True
                continue
            dst.write(existing.rstrip("\n") + "\n")
    try:
        temp_path.replace(path)
    except PermissionError:
        with temp_path.open("r", encoding="utf-8", errors="replace") as src, path.open(
            "w", encoding="utf-8", newline=""
        ) as dst:
            for chunk in src:
                dst.write(chunk)
        try:
            temp_path.unlink(missing_ok=True)
        except PermissionError:
            pass


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
        "stop_triggered": False,
        "stop_status": "not_triggered",
        "stop_pnl": 0.0,
        "after_pnl": round(base_pnl, 4),
        "after_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "delta_pnl": 0.0,
    }
    if not bars:
        result["stop_status"] = "missing_ohlcv_rows"
        return result
    if entry_idx is None or exit_idx is None or entry_price is None or entry_price <= 0:
        result["stop_status"] = "missing_entry_or_exit_bar"
        return result
    stop_price = entry_price * (1.0 - STOP_LOSS_PCT)
    for idx in range(entry_idx, exit_idx + 1):
        row = bars[idx]
        low = _field(row, "Low")
        open_price = _field(row, "Open")
        if low is None or low > stop_price:
            continue
        if open_price is not None and open_price < stop_price:
            raw_exit = open_price
            stop_fill_type = "gap_open_below_stop"
        else:
            raw_exit = stop_price
            stop_fill_type = "intraday_stop_touch"
        stop_exit_price = raw_exit * (1.0 - EXIT_SLIPPAGE_BPS / 10000.0)
        stop_return = stop_exit_price / entry_price - 1.0
        stop_pnl = base_notional * stop_return
        delta_pnl = stop_pnl - base_pnl
        result.update(
            {
                "stop_triggered": True,
                "stop_status": "stopped_at_7_5pct_max_loss",
                "stop_date": _row_date(row),
                "stop_price": round(stop_price, 4),
                "stop_raw_exit": round(raw_exit, 4),
                "stop_exit_price": round(stop_exit_price, 4),
                "stop_fill_type": stop_fill_type,
                "stop_return": round(stop_return, 6),
                "stop_pnl": round(stop_pnl, 4),
                "after_pnl": round(stop_pnl, 4),
                "after_pnl_pct": round(stop_pnl / base_notional, 6) if base_notional else None,
                "delta_pnl": round(delta_pnl, 4),
            }
        )
        return result
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
            "triggered_count": sum(1 for row in window_rows if row.get("stop_triggered")),
        }
    before_all = _metric_summary(rows, "base_pnl")
    after_all = _metric_summary(rows, "after_pnl")
    triggered_rows = [row for row in rows if row.get("stop_triggered")]
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
        "stop": {
            "triggered_count": len(triggered_rows),
            "triggered_rate": round(len(triggered_rows) / len(rows), 6) if rows else 0.0,
            "status_counts": dict(sorted(Counter(row["stop_status"] for row in rows).items())),
            "total_stop_delta_pnl": round(sum(deltas), 4),
            "avg_stop_delta_pnl": round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
            "beneficial_stop_count": sum(1 for delta in deltas if delta > 0),
            "harmful_stop_count": sum(1 for delta in deltas if delta < 0),
            "max_single_positive_delta_share": round(max_single_positive_delta_share, 6)
            if max_single_positive_delta_share is not None
            else None,
        },
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str, dict[str, Any], str]:
    aggregate = summary["aggregate"]
    stop = summary["stop"]
    pnl_delta = aggregate["delta"]["total_pnl"]
    ev_proxy_delta = aggregate["delta"]["expected_value_proxy"]
    windows_regressed = [
        window
        for window, row in summary["by_window"].items()
        if row["delta"]["total_pnl"] < -1e-6
    ]
    concentration_ok = (
        stop["max_single_positive_delta_share"] is not None
        and stop["max_single_positive_delta_share"] < MAX_SINGLE_POSITIVE_DELTA_SHARE
    )
    passed = (
        pnl_delta > 0
        and ev_proxy_delta > 0
        and not windows_regressed
        and stop["triggered_count"] >= MIN_TRIGGERED_TRADES
        and concentration_ok
    )
    evidence = {
        "aggregate_total_pnl_delta": pnl_delta,
        "expected_value_proxy_delta": ev_proxy_delta,
        "triggered_count": stop["triggered_count"],
        "triggered_count_min": MIN_TRIGGERED_TRADES,
        "windows_regressed": windows_regressed,
        "max_single_positive_delta_share": stop["max_single_positive_delta_share"],
        "max_single_positive_delta_share_max": MAX_SINGLE_POSITIVE_DELTA_SHARE,
        "shadow_gate_passed": passed,
    }
    if passed:
        return (
            "observed_only_promising_kova_max_loss_stop_needs_full_replay",
            "observed_only",
            evidence,
            (
                "The fixed maximum-loss stop improved the closed-trade shadow "
                "EV proxy and PnL without window PnL regression. Treat as a "
                "candidate for a full gap-aware, slot-aware exit replay, not "
                "as a production change."
            ),
        )
    if pnl_delta <= 0 or ev_proxy_delta <= 0:
        reason = "aggregate PnL or EV proxy did not improve"
    elif windows_regressed:
        reason = "one or more canonical windows regressed"
    elif stop["triggered_count"] < MIN_TRIGGERED_TRADES:
        reason = "sample too small"
    else:
        reason = "positive delta concentration failed"
    return (
        "rejected_kova_max_loss_stop_shadow_replay",
        "rejected",
        evidence,
        (
            "The fixed maximum-loss stop failed Gate 4 because "
            f"{reason}. No Kova max-loss stop rule should be promoted from "
            "this shadow replay."
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
            "Kova style fixed maximum loss stop at roughly 7 to 8 percent from "
            "entry may reduce tail losers in the accepted VCP top-2 paper "
            "sleeve without damaging valid breakouts as much as the prior "
            "entry-day-low stop."
        ),
        "change_type": "exit_shadow_replay",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "parameters": {
            "stop_loss_pct": STOP_LOSS_PCT,
            "stop_level": "entry_price * (1 - 0.075)",
            "daily_fill_approximation": "if open below stop use open, else use stop when low touches",
            "exit_slippage_bps": EXIT_SLIPPAGE_BPS,
        },
        "acceptance_standard": (
            "Accept only as observed candidate if aggregate closed-trade PnL "
            "and EV proxy both improve, no canonical window PnL regresses, at "
            "least 10 trades trigger, and max single positive delta share stays "
            "below 40%. Strategy promotion would still require a full "
            "gap-aware, slot-aware backtester replay."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "A fixed Kova-style max-loss stop may cut VCP tail losers "
                "without using entry-day-low geometry."
            ),
            "1_category": "exit",
            "1_playbook_alignment": (
                "This is a Kova lifecycle direction tested as shadow replay; "
                "no production exit rule changes."
            ),
            "2_history_check": {
                "exp-20260417-002": "Broad trailing stop sweeps were rejected.",
                "exp-20260422-002": "Fast-confirm breakout exit was rejected.",
                "exp-20260526-007": "Accepted VCP top-2 rank-notional paper sleeve is the source population.",
                "exp-20260526-037": "Kova stop/R ideas were marked lifecycle-policy gated.",
                "exp-20260527-016": "Entry-day-low minus 2% stop shadow replay was rejected.",
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
            "required_ohlcv_fields": ["Date", "Open", "Low"],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_trade_count": len(trades),
            "triggered_stop_count": summary["stop"]["triggered_count"],
            "core_survival_changed": False,
            "note": "No filter is added; this only shadows a stop exit on existing source trades.",
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
        "stop_metrics": summary["stop"],
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
            "exp_20260527_910_kova_max_loss_stop_shadow_replay.py"
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
        "| window | stopped | before pnl | after pnl | delta pnl | delta EV proxy |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for window, row in payload["window_metrics"].items():
        lines.append(
            "| {window} | {stopped} | {before} | {after} | {delta} | {ev_delta} |".format(
                window=window,
                stopped=row["triggered_count"],
                before=row["before"]["total_pnl"],
                after=row["after"]["total_pnl"],
                delta=row["delta"]["total_pnl"],
                ev_delta=row["delta"]["expected_value_proxy"],
            )
        )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Kova Fixed Max-Loss Stop Shadow Replay",
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
        f"- Stopped trades: `{payload['stop_metrics']['triggered_count']}`.",
        f"- Beneficial stops: `{payload['stop_metrics']['beneficial_stop_count']}`.",
        f"- Harmful stops: `{payload['stop_metrics']['harmful_stop_count']}`.",
        f"- Max single positive delta share: `{payload['stop_metrics']['max_single_positive_delta_share']}`.",
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
        "mechanism_family": "kova_loss_cutting_exit",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 6),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_vcp_trade_exit_shadow_replay",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260527_910_kova_max_loss_stop_shadow_replay.py")),
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
            "data/experiments/exp-20260527-017/broad_market_sector_open_crowding_haircut.json",
        ],
        "locked_variables": [
            "Kova fixed max-loss stop shadow variable only",
            "entries",
            "ranking",
            "sizing",
            "universe",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
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
                "stop": payload["stop_metrics"],
                "gate4": payload["gate4"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
