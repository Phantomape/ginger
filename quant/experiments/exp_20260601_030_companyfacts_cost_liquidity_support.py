"""exp-20260601-030: Companyfacts cost-liquidity paper support.

This tests one production-visible free OHLCV execution-quality field on top of
the accepted Companyfacts gross-margin plus filing-timeliness Fundamental
Growth + RS paper adapter. It is a default-off paper scout and emits no live
orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_027_companyfacts_filing_timeliness_support as prev  # noqa: E402


EXPERIMENT_ID = "exp-20260601-030"
STEM = "companyfacts_cost_liquidity_support"
TRIAL_FAMILY = "companyfacts_cost_liquidity_support"
CHANGED_VARIABLE = "companyfacts_cost_liquidity_support_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = "exp-20260601-026"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260601_026_companyfacts_gross_margin_rs_adapter.json"
)

MIN_DOLLAR_VOLUME = 200_000_000.0
MAX_SIGNAL_DAY_RANGE_PCT = 0.10
SUPPORT_SCALAR = 1.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_030_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    return prev._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return prev._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return prev._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    prev._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    prev._write_text(path, text)


def _as_float(value: Any) -> float | None:
    return prev._as_float(value)


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _load_source_payload() -> dict[str, Any]:
    with SOURCE_ARTIFACT.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _source_target_rows_by_window(source_payload: dict[str, Any]) -> OrderedDict[str, list[dict[str, Any]]]:
    rows_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    raw = source_payload.get("target_trades_by_window") or {}
    for label in prev.base_exp.base.WINDOWS:
        rows_by_window[label] = [dict(row) for row in raw.get(label) or []]
    return rows_by_window


def _load_ohlcv_index_by_window() -> OrderedDict[str, dict[str, dict[str, dict[str, Any]]]]:
    out: OrderedDict[str, dict[str, dict[str, dict[str, Any]]]] = OrderedDict()
    for label, cfg in prev.base_exp.base.WINDOWS.items():
        snapshot_path = ROOT / cfg["snapshot"]
        with snapshot_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        raw_ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else payload
        ticker_index: dict[str, dict[str, dict[str, Any]]] = {}
        for ticker, rows in (raw_ohlcv or {}).items():
            day_index: dict[str, dict[str, Any]] = {}
            for row in rows or []:
                day = str(row.get("Date") or row.get("date") or "")[:10]
                if day:
                    day_index[day] = row
            ticker_index[str(ticker).upper()] = day_index
        out[label] = ticker_index
    return out


def _cost_liquidity_context(
    row: dict[str, Any],
    ohlcv_index: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    price_row = (ohlcv_index.get(ticker) or {}).get(signal_date)
    dollar_volume = _as_float(row.get("avg_dollar_volume_20"))
    status = "ok"
    signal_range_pct = None
    high = low = close = volume = None
    if not price_row:
        status = "missing_signal_day_ohlcv"
    else:
        high = _as_float(price_row.get("High") or price_row.get("high"))
        low = _as_float(price_row.get("Low") or price_row.get("low"))
        close = _as_float(price_row.get("Close") or price_row.get("close"))
        volume = _as_float(price_row.get("Volume") or price_row.get("volume"))
        if close is None or close <= 0.0 or high is None or low is None:
            status = "invalid_signal_day_ohlcv"
        else:
            signal_range_pct = (high - low) / close
    if dollar_volume is None:
        status = "missing_avg_dollar_volume_20" if status == "ok" else status
    passed = (
        status == "ok"
        and dollar_volume is not None
        and signal_range_pct is not None
        and dollar_volume >= MIN_DOLLAR_VOLUME
        and signal_range_pct <= MAX_SIGNAL_DAY_RANGE_PCT
    )
    return {
        "companyfacts_cost_liquidity_rule_version": RULE_VERSION,
        "companyfacts_cost_liquidity_known_at": "signal-day OHLCV and trailing dollar volume <= signal_date close",
        "companyfacts_cost_liquidity_trade_enabled": False,
        "companyfacts_cost_liquidity_alters_orders": False,
        "companyfacts_cost_liquidity_status": status,
        "companyfacts_cost_liquidity_pass_v1": passed,
        "companyfacts_cost_liquidity_support_scalar": SUPPORT_SCALAR if passed else 1.0,
        "companyfacts_cost_liquidity_min_dollar_volume": MIN_DOLLAR_VOLUME,
        "companyfacts_cost_liquidity_max_signal_day_range_pct": MAX_SIGNAL_DAY_RANGE_PCT,
        "companyfacts_signal_day_high": _round(high, 6),
        "companyfacts_signal_day_low": _round(low, 6),
        "companyfacts_signal_day_close": _round(close, 6),
        "companyfacts_signal_day_volume": _round(volume, 2),
        "companyfacts_signal_day_range_pct": _round(signal_range_pct, 6),
        "companyfacts_avg_dollar_volume_20": _round(dollar_volume, 2),
    }


def _select_supported_trades(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    ohlcv_by_window: OrderedDict[str, dict[str, dict[str, dict[str, Any]]]],
) -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    before_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    after_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts: OrderedDict[str, dict[str, int]] = OrderedDict()
    supported_counts: OrderedDict[str, int] = OrderedDict()
    sample: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for label, rows in rows_by_window.items():
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        incremental_rows: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        samples_for_window: list[dict[str, Any]] = []
        for row in rows:
            base_pnl = _as_float(row.get("pnl"))
            if base_pnl is None:
                continue
            timeliness = prev._timeliness_context(row)
            timeliness_scalar = prev.SUPPORT_SCALAR if timeliness["filing_timeliness_pass_v1"] else 1.0
            before_pnl = base_pnl * timeliness_scalar
            context = _cost_liquidity_context(row, ohlcv_by_window[label])
            counts[context["companyfacts_cost_liquidity_status"]] = (
                counts.get(context["companyfacts_cost_liquidity_status"], 0) + 1
            )
            before_trade = {
                **row,
                **timeliness,
                **context,
                "rule_version": RULE_VERSION,
                "strategy": "companyfacts_gross_margin_filing_timeliness_rs_candidate_pool",
                "pnl": _round(before_pnl, 2),
                "paper_pnl": _round(before_pnl, 2),
                "pnl_without_companyfacts_cost_liquidity_support": _round(before_pnl, 2),
                "paper_pnl_source": "pnl_with_filing_timeliness_without_companyfacts_cost_liquidity_support",
                "trade_enabled": False,
                "alters_orders": False,
            }
            cost_scalar = SUPPORT_SCALAR if context["companyfacts_cost_liquidity_pass_v1"] else 1.0
            after_pnl = before_pnl * cost_scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_cost_liquidity_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["companyfacts_cost_liquidity_pass_v1"]:
                incremental_pnl = after_pnl - before_pnl
                incremental = {
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "companyfacts_cost_liquidity_incremental_support",
                }
                incremental_rows.append(incremental)
                if len(samples_for_window) < 20:
                    samples_for_window.append(after_trade)
        before_by_window[label] = before_rows
        after_by_window[label] = after_rows
        incremental_by_window[label] = incremental_rows
        status_counts[label] = dict(sorted(counts.items()))
        supported_counts[label] = len(incremental_rows)
        sample[label] = samples_for_window

    diagnostics = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "source_artifact": _repo_rel(SOURCE_ARTIFACT),
        "source_target_trade_count_by_window": {
            label: len(rows) for label, rows in rows_by_window.items()
        },
        "supported_trade_count_by_window": supported_counts,
        "cost_liquidity_status_counts_by_window": status_counts,
        "supported_trade_sample_by_window": sample,
    }
    return before_by_window, after_by_window, incremental_by_window, diagnostics


def _run_window_metrics(
    baselines: OrderedDict[str, dict[str, Any]],
    before_by_window: OrderedDict[str, list[dict[str, Any]]],
    after_by_window: OrderedDict[str, list[dict[str, Any]]],
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in prev.base_exp.base.WINDOWS.items():
        before_result = baselines[label]["result"]
        before_overlay = prev.base_exp.base._overlay_from_paper_trades(before_result, before_by_window[label])
        after_overlay = prev.base_exp.base._overlay_from_paper_trades(before_result, after_by_window[label])
        before = prev.base_exp.base.overlay_helper._metrics_with_overlay(before_result, before_overlay)
        after = prev.base_exp.base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = prev.base_exp.base.overlay_helper._delta(after, before)
        rows[label] = {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "before": before,
            "after": after,
            "delta": delta,
            "source_trade_count": len(before_by_window[label]),
            "target_trade_count": len(incremental_by_window[label]),
            "target_trade_pnl_usd": _round(sum(float(row.get("pnl") or 0.0) for row in incremental_by_window[label]), 2),
            "overlay_total_pnl_before": before_overlay["overlay_total_pnl"],
            "overlay_total_pnl_after": after_overlay["overlay_total_pnl"],
        }
    return rows


def _aggregate(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    return prev._aggregate(window_rows)


def _target_summary(incremental_by_window: OrderedDict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return prev._target_summary(incremental_by_window)


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_windows = [
        label for label, row in window_rows.items()
        if float(row["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_windows = [
        label for label, row in window_rows.items()
        if float(row["delta"].get("total_pnl") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(float(row["delta"].get("max_drawdown_pct") or 0.0) for row in window_rows.values())
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values())
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for rows in target_summary["trades_by_window"].values() if rows > 0)
    concentration_passed = (
        float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
        and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI
    )
    gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", float(aggregate["delta"]["expected_value_score"]) > 0.0),
            ("aggregate_pnl_positive", float(aggregate["delta"]["total_pnl"]) > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows) == len(window_rows)),
            ("all_windows_pnl_improved", len(pnl_windows) == len(window_rows)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            ("concentration_guard_passed", concentration_passed),
        ]
    )
    failed = [name for name, passed in gates.items() if not passed]
    alpha_passed = not failed
    decision = (
        "accepted_shared_companyfacts_cost_liquidity_support"
        if alpha_passed
        else "rejected_companyfacts_cost_liquidity_support"
    )
    rationale = (
        "Companyfacts cost-liquidity support passed the three-window alpha gate and is retained in the shared default-off paper adapter with no live order impact."
        if alpha_passed
        else "Companyfacts cost-liquidity support failed Gate 4; no shared strategy or production behavior is retained."
    )
    return {
        "passed": alpha_passed,
        "alpha_passed": alpha_passed,
        "promotable_now": alpha_passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_shared_adapter_before_promotion": False,
        "requires_parity_before_promotion": False,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Cost-Liquidity Support",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- incremental target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | adjusted trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_results"].items():
        lines.append(
            f"| {label} | {row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['delta']['expected_value_score']:+.4f} | "
            f"${row['delta']['total_pnl']:+,.2f} | {row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Parity",
            "",
            "This replay uses only signal-day OHLCV and existing Companyfacts target rows "
            "known after signal-date close and before next-open paper entry. No live/default "
            "orders, core ranking, core sizing, exits, LLM, or news path changed.",
            "",
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Top Positive Incremental Contributors",
            "",
            "| ticker | trades | incremental PnL | positive PnL share |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in target["ticker_rows"][:10]:
        lines.append(
            f"| {row['ticker']} | {row['trade_count']} | "
            f"${row['paper_pnl_usd']:,.2f} | {row['positive_pnl_share']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Companyfacts cost-liquidity support",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            f"- Incremental target trades: {payload['target_trade_summary']['target_trade_count']}",
            "- Production impact: shared default-off paper adapter updated; no live orders changed.",
            "",
        ]
    )


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "failed_gates": payload["gate4"]["failed_gates"],
        "metrics": {
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
    }
    _write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["decision"]
            item["completed_at"] = payload["timestamp"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["report_file"] = _repo_rel(ARTIFACT_MD)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["delta"]["expected_value_score"]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["delta"]["strategy_total_pnl"]
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _append_log_record(record: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if EXPERIMENT_LOG.exists():
        with EXPERIMENT_LOG.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if f'"experiment_id": "{EXPERIMENT_ID}"' in line:
                    continue
                kept.append(line.rstrip("\n"))
    kept.append(json.dumps(_safe(record), ensure_ascii=True, sort_keys=True))
    tmp = EXPERIMENT_LOG.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for line in kept:
            if line:
                handle.write(line + "\n")
    tmp.replace(EXPERIMENT_LOG)


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = prev.base_exp.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_payload = _load_source_payload()
    source_rows_by_window = _source_target_rows_by_window(source_payload)
    ohlcv_by_window = _load_ohlcv_index_by_window()
    before_by_window, after_by_window, incremental_by_window, selection_diagnostics = _select_supported_trades(
        source_rows_by_window,
        ohlcv_by_window,
    )
    baselines = prev.base_exp._load_baselines()
    window_rows = _run_window_metrics(baselines, before_by_window, after_by_window, incremental_by_window)
    aggregate = _aggregate(window_rows)
    target_summary = _target_summary(incremental_by_window)
    gate4 = _gate4(aggregate, window_rows, target_summary)
    timestamp = _utc_now()
    ticket = _load_ticket()
    accepted = bool(gate4["alpha_passed"])
    production_impact = {
        "replay_only": False if accepted else True,
        "default_off_paper_only": True,
        "shared_policy_changed": accepted,
        "run_adapter_changed": accepted,
        "backtester_adapter_changed": False,
        "parity_test_added": accepted,
        "trade_enabled": False,
        "alters_orders": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "production_watchlist_changed": False,
        "llm_or_news_changed": False,
    }
    ticket_snapshot = dict(ticket)
    ticket_snapshot["status"] = "completed"
    ticket_snapshot["completed_at"] = timestamp
    ticket_snapshot["result"] = {
        "decision": gate4["decision"],
        "accepted": accepted,
        "alpha_passed": gate4["alpha_passed"],
        "promotable_now": gate4["promotable_now"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "failed_gates": gate4["failed_gates"],
        "metrics": {
            "aggregate_expected_value_delta": aggregate["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": aggregate["delta"]["total_pnl"],
            "target_trade_count": target_summary["target_trade_count"],
            "max_single_positive_share": target_summary["max_single_positive_share"],
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
        },
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": gate4["decision"],
        "lane": "alpha_search",
        "decision": gate4["decision"],
        "accepted": accepted,
        "hypothesis": (
            "Accepted Companyfacts gross-margin plus filing-timeliness paper candidates may have cleaner "
            "replacement value when signal-day dollar liquidity is high and intraday range is contained."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "companyfacts_cost_liquidity_support",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260601-026",
            "exp-20260601-027",
            "exp-20260529-004",
            "exp-20260601-029",
            "exp-20260601-017",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_ohlcv_cost_liquidity_field_on_accepted_companyfacts_adapter",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "baseline_before_state": "accepted exp-20260601-027 filing-timeliness support reconstructed from exp-026 target rows",
            "min_dollar_volume": MIN_DOLLAR_VOLUME,
            "max_signal_day_range_pct": MAX_SIGNAL_DAY_RANGE_PCT,
            "support_scalar": SUPPORT_SCALAR,
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "before_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
        "after_metrics": OrderedDict((label, row["after"]) for label, row in window_rows.items()),
        "delta_metrics": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
        "aggregate": aggregate,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "selection_diagnostics": selection_diagnostics,
        "gate1": {
            "passed": True,
            "baseline_source": "current PIT-DTE canonical backtests plus accepted exp-20260601-027 filing-timeliness overlay",
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "target_trades_by_window avg_dollar_volume_20",
                "canonical OHLCV snapshot signal_date High",
                "canonical OHLCV snapshot signal_date Low",
                "canonical OHLCV snapshot signal_date Close",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": True,
            "note": "No core production filter was added; default-off paper support only.",
            "signals_generated_survived_by_window": {
                label: {
                    "signals_generated": row["after"].get("signals_generated"),
                    "signals_survived": row["after"].get("signals_survived"),
                    "survival_rate": row["after"].get("survival_rate"),
                }
                for label, row in window_rows.items()
            },
        },
        "gate4": gate4,
        "gate_questions": {
            "1_alpha_hypothesis": "candidate_pool / default-off paper allocation: high dollar liquidity plus contained range may improve Companyfacts paper execution quality.",
            "2_history_check": {
                "exp-20260529-004": "VBB cost-liquidity support accepted.",
                "exp-20260601-029": "FINRA/IWM cost-liquidity support accepted.",
                "exp-20260601-017": "Consensus liquidity-efficiency gate rejected.",
                "exp-20260601-026/027": "Companyfacts gross-margin source and filing-timeliness support accepted; no Companyfacts cost-liquidity support tested.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "docs/backtesting.md three PIT-DTE windows, using accepted filing-timeliness adapter as before; require aggregate EV/PnL positive, all windows improved, drawdown drift <=0.5pp, survival >=5%, sample and concentration guards.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260601_030_companyfacts_cost_liquidity_support.py",
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact,
        "ticket": ticket_snapshot,
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "closed forward replacement-value rows before any live activation",
            "no Companyfacts cost-liquidity threshold/scalar retune on the same frozen windows",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            "quant/fundamental_growth_rs_paper_sleeve.py",
            "quant/test_fundamental_growth_rs_paper_sleeve.py",
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
            "docs/data_edge_context_layers.md",
            "docs/production_backtest_parity.md",
        ],
        "anti_js": "No JavaScript was used.",
    }


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(
        BEFORE_JSON,
        {
            **payload["aggregate"]["before"],
            "windows": payload["before_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "before_aggregate",
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
        },
    )
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))
    _write_text(CARD_MD, _card(payload))
    _update_ticket(payload)
    _update_registry(payload)

    prediction = (payload.get("ticket") or {}).get("prediction") or {}
    actual_success = 1 if payload["gate4"]["alpha_passed"] else 0
    predicted_probability = prediction.get("success_probability")
    calibration = {
        "actual_decision": payload["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": predicted_probability,
        "brier_score": _round((float(predicted_probability) - actual_success) ** 2, 6)
        if predicted_probability is not None
        else None,
        "actual_ev_delta": payload["aggregate"]["delta"]["expected_value_score"],
        "actual_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": payload["gate4"]["failed_gates"],
        "predicted_failure_mode_hit": bool(
            set(prediction.get("main_failure_modes") or []) & set(payload["gate4"]["failed_gates"])
        ),
    }
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "prediction": prediction,
        "calibration": calibration,
        "before_metrics": payload["aggregate"]["before"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": {
            **payload["aggregate"]["delta"],
            "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
            "max_single_positive_share": payload["target_trade_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_trade_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": label,
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["delta"]["expected_value_score"],
                "strategy_total_pnl_delta": row["delta"]["total_pnl"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for label, row in payload["window_results"].items()
        ],
        "production_impact": payload["production_impact"],
        "decision_basis": payload["gate4"],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }
    _append_log_record(log_record)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "target_trade_count",
                        "target_trade_pnl_usd",
                        "max_single_positive_share",
                        "positive_pnl_hhi",
                        "trades_by_window",
                        "pnl_by_window",
                    )
                },
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
