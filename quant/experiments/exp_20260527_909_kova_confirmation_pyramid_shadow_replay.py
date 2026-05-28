"""exp-20260527-909: Kova confirmation pyramid shadow replay.

Kova-style pyramiding adds only after a position starts working. This script
tests one closed-trade shadow variable on the accepted exp-20260526-007 VCP
top-2 paper sleeve:

- If a trade closes at least 3% above entry within the first five trading days,
  add 50% of its original paper notional at the next open.
- Exit the add-on at the same source exit date.

No production strategy, backtester, ranking, entry, exit, universe, LLM/news,
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


EXPERIMENT_ID = "exp-20260527-909"
STEM = "kova_confirmation_pyramid_shadow_replay"
OUT_JSON_NAME = "exp_20260527_909_kova_confirmation_pyramid_shadow_replay.json"
TRIAL_FAMILY = "kova_confirmation_pyramid_shadow_replay"
CHANGED_VARIABLE = "kova_confirmation_pyramid_addon_50pct_v1"
RULE_VERSION = "kova_confirmation_close_gt_entry_3pct_addon_50pct_v1"
SOURCE_VARIANT = "rank2_125"

CONFIRM_CLOSE_GAIN = 0.03
CONFIRM_WITHIN_TRADING_DAYS = 5
ADDON_NOTIONAL_FRACTION = 0.50
ENTRY_SLIPPAGE_BPS = 5.0
EXIT_SLIPPAGE_BPS = 5.0
MIN_TRIGGERED_TRADES = 20
MIN_DELTA_PNL_PCT = 0.10
MAX_SINGLE_POSITIVE_SHARE = 0.40

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
    result = {
        "window": window,
        "ticker": ticker,
        "signal_date": _date10(trade.get("signal_date") or trade.get("date")),
        "entry_date": entry_date,
        "exit_date": exit_date,
        "base_notional": round(base_notional, 4),
        "base_pnl": round(base_pnl, 4),
        "base_pnl_pct": round(base_pnl / base_notional, 6) if base_notional else None,
        "addon_triggered": False,
        "addon_status": "not_triggered",
        "addon_notional": 0.0,
        "addon_pnl": 0.0,
        "after_pnl": round(base_pnl, 4),
        "after_deployed_notional": round(base_notional, 4),
    }
    if not bars:
        result["addon_status"] = "missing_ohlcv_rows"
        return result
    if entry_idx is None or exit_idx is None or entry_price is None or entry_price <= 0:
        result["addon_status"] = "missing_entry_or_exit_bar"
        return result
    if exit_idx <= entry_idx + 1:
        result["addon_status"] = "exit_too_soon_for_next_open_add"
        return result

    trigger_idx: int | None = None
    trigger_close: float | None = None
    last_trigger_idx = min(entry_idx + CONFIRM_WITHIN_TRADING_DAYS - 1, exit_idx - 1)
    trigger_level = entry_price * (1.0 + CONFIRM_CLOSE_GAIN)
    for idx in range(entry_idx, last_trigger_idx + 1):
        close = _field(bars[idx], "Close")
        if close is not None and close >= trigger_level:
            trigger_idx = idx
            trigger_close = close
            break
    if trigger_idx is None:
        result["addon_status"] = "no_3pct_close_confirmation"
        return result

    fill_idx = trigger_idx + 1
    if fill_idx > exit_idx:
        result["addon_status"] = "confirmation_after_last_fill_day"
        return result
    fill_open = _field(bars[fill_idx], "Open")
    exit_raw_close = _num(trade.get("exit_raw_close")) or _field(bars[exit_idx], "Close")
    if fill_open is None or fill_open <= 0 or exit_raw_close is None or exit_raw_close <= 0:
        result["addon_status"] = "missing_fill_or_exit_price"
        return result
    addon_entry_price = fill_open * (1.0 + ENTRY_SLIPPAGE_BPS / 10000.0)
    addon_exit_price = exit_raw_close * (1.0 - EXIT_SLIPPAGE_BPS / 10000.0)
    addon_notional = base_notional * ADDON_NOTIONAL_FRACTION
    addon_return = addon_exit_price / addon_entry_price - 1.0
    addon_pnl = addon_notional * addon_return
    after_pnl = base_pnl + addon_pnl
    result.update(
        {
            "addon_triggered": True,
            "addon_status": "added_next_open_after_3pct_close_confirmation",
            "confirm_date": _row_date(bars[trigger_idx]),
            "confirm_close": round(trigger_close or 0.0, 4),
            "confirm_gain_vs_entry": round((trigger_close or 0.0) / entry_price - 1.0, 6),
            "addon_entry_date": _row_date(bars[fill_idx]),
            "addon_entry_raw_open": round(fill_open, 4),
            "addon_entry_price": round(addon_entry_price, 4),
            "addon_exit_price": round(addon_exit_price, 4),
            "addon_notional": round(addon_notional, 4),
            "addon_return": round(addon_return, 6),
            "addon_pnl": round(addon_pnl, 4),
            "after_pnl": round(after_pnl, 4),
            "after_deployed_notional": round(base_notional + addon_notional, 4),
        }
    )
    return result


def _metric_summary(rows: list[dict[str, Any]], pnl_key: str, notional_key: str) -> dict[str, Any]:
    pnls = [float(row.get(pnl_key) or 0.0) for row in rows]
    notionals = [float(row.get(notional_key) or 0.0) for row in rows]
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
        "total_deployed_notional": round(total_notional, 4),
        "return_on_deployed_notional": round(ret_pct, 6),
        "avg_pnl": round(total_pnl / len(rows), 4) if rows else 0.0,
        "win_rate": round(sum(1 for pnl in pnls if pnl > 0) / len(pnls), 6) if pnls else 0.0,
        "trade_sharpe_proxy": round(trade_sharpe_proxy, 6),
        "expected_value_proxy": round(ret_pct * trade_sharpe_proxy, 6),
    }


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label in WINDOWS:
        window_rows = [row for row in rows if row.get("window") == label]
        before = _metric_summary(window_rows, "base_pnl", "base_notional")
        after = _metric_summary(window_rows, "after_pnl", "after_deployed_notional")
        by_window[label] = {
            "before": before,
            "after": after,
            "delta": {
                "total_pnl": round(after["total_pnl"] - before["total_pnl"], 4),
                "expected_value_proxy": round(
                    after["expected_value_proxy"] - before["expected_value_proxy"], 6
                ),
                "return_on_deployed_notional": round(
                    after["return_on_deployed_notional"]
                    - before["return_on_deployed_notional"],
                    6,
                ),
            },
            "triggered_count": sum(1 for row in window_rows if row.get("addon_triggered")),
        }
    before_all = _metric_summary(rows, "base_pnl", "base_notional")
    after_all = _metric_summary(rows, "after_pnl", "after_deployed_notional")
    triggered_rows = [row for row in rows if row.get("addon_triggered")]
    addon_pnls = [float(row.get("addon_pnl") or 0.0) for row in triggered_rows]
    positive_addons = [pnl for pnl in addon_pnls if pnl > 0]
    positive_sum = sum(positive_addons)
    max_single_positive_share = (
        max(positive_addons) / positive_sum if positive_sum > 0 and positive_addons else None
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
                "return_on_deployed_notional": round(
                    after_all["return_on_deployed_notional"]
                    - before_all["return_on_deployed_notional"],
                    6,
                ),
            },
        },
        "by_window": by_window,
        "addon": {
            "triggered_count": len(triggered_rows),
            "triggered_rate": round(len(triggered_rows) / len(rows), 6) if rows else 0.0,
            "status_counts": dict(sorted(Counter(row["addon_status"] for row in rows).items())),
            "total_addon_pnl": round(sum(addon_pnls), 4),
            "avg_addon_pnl": round(sum(addon_pnls) / len(addon_pnls), 4) if addon_pnls else 0.0,
            "addon_win_rate": round(sum(1 for pnl in addon_pnls if pnl > 0) / len(addon_pnls), 6)
            if addon_pnls
            else 0.0,
            "max_single_positive_addon_share": round(max_single_positive_share, 6)
            if max_single_positive_share is not None
            else None,
        },
    }


def _decision(summary: dict[str, Any]) -> tuple[str, str, dict[str, Any], str]:
    aggregate = summary["aggregate"]
    addon = summary["addon"]
    delta_pct = aggregate["delta"]["total_pnl_delta_pct"]
    ev_proxy_delta = aggregate["delta"]["expected_value_proxy"]
    return_on_deployed_delta = aggregate["delta"]["return_on_deployed_notional"]
    windows_regressed = [
        window
        for window, row in summary["by_window"].items()
        if row["delta"]["total_pnl"] < -1e-6
    ]
    concentration_ok = (
        addon["max_single_positive_addon_share"] is not None
        and addon["max_single_positive_addon_share"] < MAX_SINGLE_POSITIVE_SHARE
    )
    risk_adjusted_ok = ev_proxy_delta >= 0 and return_on_deployed_delta >= 0
    passed = (
        delta_pct is not None
        and delta_pct >= MIN_DELTA_PNL_PCT
        and not windows_regressed
        and addon["triggered_count"] >= MIN_TRIGGERED_TRADES
        and concentration_ok
        and risk_adjusted_ok
    )
    evidence = {
        "aggregate_total_pnl_delta_pct": delta_pct,
        "aggregate_total_pnl_delta_pct_min": MIN_DELTA_PNL_PCT,
        "expected_value_proxy_delta": ev_proxy_delta,
        "return_on_deployed_notional_delta": return_on_deployed_delta,
        "risk_adjusted_proxy_non_regression_required": True,
        "triggered_count": addon["triggered_count"],
        "triggered_count_min": MIN_TRIGGERED_TRADES,
        "windows_regressed": windows_regressed,
        "max_single_positive_addon_share": addon["max_single_positive_addon_share"],
        "max_single_positive_addon_share_max": MAX_SINGLE_POSITIVE_SHARE,
        "shadow_gate_passed": passed,
    }
    if passed:
        return (
            "observed_only_promising_kova_confirmation_pyramid_needs_full_replay",
            "observed_only",
            evidence,
            (
                "The confirmation add-on shadow replay improved aggregate PnL "
                "without window PnL regression. Treat as a candidate for a full "
                "slot-aware backtester replay, not as a production change."
            ),
        )
    if delta_pct is not None and delta_pct > 0 and not risk_adjusted_ok:
        return (
            "rejected_pnl_positive_but_ev_proxy_regressed_kova_confirmation_pyramid",
            "rejected",
            evidence,
            (
                "The confirmation add-on increased closed-trade PnL, but the "
                "risk-adjusted EV proxy and/or return on deployed notional "
                "regressed. No Kova pyramiding rule should be promoted from "
                "this capital-only lift."
            ),
        )
    return (
        "rejected_kova_confirmation_pyramid_shadow_replay",
        "rejected",
        evidence,
        (
            "The confirmation add-on shadow replay did not clear the strict "
            "closed-trade gate. No Kova pyramiding rule should be promoted from "
            "this result."
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
            "Kova-style pyramiding after price confirmation may improve the "
            "accepted VCP top-2 sleeve by adding limited notional only after "
            "the entry works, while avoiding adds to failed breakouts."
        ),
        "change_type": "capital_allocation_shadow_replay",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": RULE_VERSION,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "parameters": {
            "confirm_close_gain": CONFIRM_CLOSE_GAIN,
            "confirm_within_trading_days": CONFIRM_WITHIN_TRADING_DAYS,
            "addon_notional_fraction": ADDON_NOTIONAL_FRACTION,
            "addon_fill": "next_open_after_confirming_close",
            "addon_exit": "same_source_exit_date",
            "entry_slippage_bps": ENTRY_SLIPPAGE_BPS,
            "exit_slippage_bps": EXIT_SLIPPAGE_BPS,
        },
        "acceptance_standard": (
            "Accept only as an observed candidate if aggregate closed-trade "
            "PnL improves by at least 10%, no canonical window PnL regresses, "
            "at least 20 trades trigger, and max single positive add-on "
            "contribution stays below 40%, while risk-adjusted EV proxy and "
            "return on deployed notional do not regress. Strategy promotion "
            "would still require a full slot-aware backtester replay."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Kova pyramiding may add exposure only to VCP trades that are "
                "already confirming."
            ),
            "1_category": "capital_allocation",
            "1_playbook_alignment": (
                "This is a Kova lifecycle direction that does not require new "
                "non-OHLCV sidecar data, but it is tested only as shadow replay."
            ),
            "2_history_check": {
                "exp-20260428-005": "Prior add-on materiality accepted a day-2 add-on family.",
                "exp-20260428-006": "Prior add-on cap variants were rejected.",
                "exp-20260501-022": "Second add-on work exists as separate lifecycle research.",
                "exp-20260526-007": "Accepted VCP top-2 rank-notional paper sleeve is the source population.",
                "exp-20260527-016": "Kova entry-day-low stop was rejected on the same VCP source trades.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Closed-trade shadow: aggregate PnL delta >=10%, zero window "
                "PnL regression, triggered_count >=20, concentration <40%, "
                "and no risk-adjusted proxy regression."
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
                "exit_raw_close",
                "paper_notional_usd",
                "pnl",
            ],
            "required_ohlcv_fields": ["Date", "Open", "Close"],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "source_trade_count": len(trades),
            "triggered_addon_count": summary["addon"]["triggered_count"],
            "core_survival_changed": False,
            "note": "No filter is added; this only shadows add-on capital on existing source trades.",
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
        "addon_metrics": summary["addon"],
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
            "exp_20260527_909_kova_confirmation_pyramid_shadow_replay.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "why_not_other_changes": (
            "Did not alter VCP entries, exits, rank-notional profile, ranking, "
            "universe, LLM/news, backtester, run.py, or live/default orders."
        ),
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | triggered | before pnl | after pnl | delta pnl |",
        "|---|---:|---:|---:|---:|",
    ]
    for window, row in payload["window_metrics"].items():
        lines.append(
            "| {window} | {triggered} | {before} | {after} | {delta} |".format(
                window=window,
                triggered=row["triggered_count"],
                before=row["before"]["total_pnl"],
                after=row["after"]["total_pnl"],
                delta=row["delta"]["total_pnl"],
            )
        )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Kova Confirmation Pyramid Shadow Replay",
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
        f"- Delta PnL pct: `{payload['delta_metrics']['total_pnl_delta_pct']}`.",
        f"- Delta EV proxy: `{payload['delta_metrics']['expected_value_proxy']}`.",
        f"- Delta return on deployed notional: `{payload['delta_metrics']['return_on_deployed_notional']}`.",
        f"- Triggered add-ons: `{payload['addon_metrics']['triggered_count']}`.",
        f"- Add-on win rate: `{payload['addon_metrics']['addon_win_rate']}`.",
        f"- Max single positive add-on share: `{payload['addon_metrics']['max_single_positive_addon_share']}`.",
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
        "mechanism_family": "kova_lifecycle_pyramiding",
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": existing.get("prior_trial_count", 8),
        "nearby_prior_experiments": list(payload["gate_questions"]["2_history_check"].keys()),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_vcp_trade_lifecycle_shadow_replay",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260527_909_kova_confirmation_pyramid_shadow_replay.py")),
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
            "Kova confirmation add-on shadow variable only",
            "entries",
            "exits",
            "ranking",
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
                "addon": payload["addon_metrics"],
                "gate4": payload["gate4"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
