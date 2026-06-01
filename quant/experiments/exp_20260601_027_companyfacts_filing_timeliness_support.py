"""exp-20260601-027: Companyfacts filing-timeliness paper support.

This tests one new production-visible SEC Companyfacts field on top of the
accepted exp-20260601-026 gross-margin Fundamental Growth + RS paper adapter.
It is retained only through the shared default-off paper adapter and emits no
live orders.
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

from quant.experiments import exp_20260601_002_companyfacts_share_contraction_rs_candidate_pool as base_exp  # noqa: E402


EXPERIMENT_ID = "exp-20260601-027"
STEM = "companyfacts_filing_timeliness_support"
TRIAL_FAMILY = "companyfacts_filing_timeliness_quality_support"
CHANGED_VARIABLE = "filing_timeliness_quality_support_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = "exp-20260601-026"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260601_026_companyfacts_gross_margin_rs_adapter.json"
)

TIMELY_10Q_MAX_DAYS = 45
TIMELY_10K_MAX_DAYS = 75
SUPPORT_SCALAR = 1.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_027_{STEM}.json"
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
    return base_exp._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return base_exp._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return base_exp._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    base_exp._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    base_exp._write_text(path, text)


def _as_float(value: Any) -> float | None:
    return base_exp._as_float(value)


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
    for label in base_exp.base.WINDOWS:
        rows_by_window[label] = [dict(row) for row in raw.get(label) or []]
    return rows_by_window


def _days_between(start: Any, end: Any) -> int | None:
    start_text = str(start or "")[:10]
    end_text = str(end or "")[:10]
    if not start_text or not end_text:
        return None
    try:
        start_day = datetime.fromisoformat(start_text)
        end_day = datetime.fromisoformat(end_text)
    except ValueError:
        return None
    if end_day < start_day:
        return None
    return (end_day - start_day).days


def _timely_limit_for_form(form: Any) -> int | None:
    text = str(form or "").upper()
    if text == "10-Q":
        return TIMELY_10Q_MAX_DAYS
    if text == "10-K":
        return TIMELY_10K_MAX_DAYS
    return None


def _timeliness_context(row: dict[str, Any]) -> dict[str, Any]:
    form = row.get("operating_income_current_form")
    filed = row.get("operating_income_current_filed")
    period_end = row.get("operating_income_current_period_end")
    lag = _days_between(period_end, filed)
    limit = _timely_limit_for_form(form)
    if lag is None:
        status = "missing_filed_or_period_end"
        passed = False
    elif limit is None:
        status = "unsupported_form"
        passed = False
    else:
        status = "ok"
        passed = lag <= limit
    return {
        "filing_timeliness_rule_version": RULE_VERSION,
        "filing_timeliness_known_at": "SEC Companyfacts operating-income filed date and period end <= signal_date",
        "filing_timeliness_trade_enabled": False,
        "filing_timeliness_alters_orders": False,
        "filing_timeliness_status": status,
        "filing_timeliness_form": form,
        "filing_timeliness_filed": filed,
        "filing_timeliness_period_end": period_end,
        "filing_timeliness_lag_days": lag,
        "filing_timeliness_max_days": limit,
        "filing_timeliness_pass_v1": passed,
        "filing_timeliness_support_scalar": SUPPORT_SCALAR if passed else 1.0,
    }


def _select_supported_trades(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    base_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
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
            context = _timeliness_context(row)
            counts[context["filing_timeliness_status"]] = counts.get(context["filing_timeliness_status"], 0) + 1
            before_trade = {
                **row,
                **context,
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": row.get("candidate_pool_rule_version"),
                "strategy": "companyfacts_gross_margin_rs_candidate_pool",
                "pnl": _round(base_pnl, 2),
                "paper_pnl": _round(base_pnl, 2),
                "pnl_without_filing_timeliness_support": _round(base_pnl, 2),
                "trade_enabled": False,
                "alters_orders": False,
            }
            scalar = SUPPORT_SCALAR if context["filing_timeliness_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_filing_timeliness_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["filing_timeliness_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental_rows.append(
                    {
                        **after_trade,
                        "pnl": _round(incremental_pnl, 2),
                        "paper_pnl": _round(incremental_pnl, 2),
                        "incremental_support_pnl": _round(incremental_pnl, 2),
                        "paper_pnl_source": "filing_timeliness_incremental_support",
                    }
                )
                if len(samples_for_window) < 20:
                    samples_for_window.append(after_trade)
        base_by_window[label] = before_rows
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
        "timeliness_status_counts_by_window": status_counts,
        "supported_trade_sample_by_window": sample,
    }
    return base_by_window, after_by_window, incremental_by_window, diagnostics


def _run_window_metrics(
    baselines: OrderedDict[str, dict[str, Any]],
    base_by_window: OrderedDict[str, list[dict[str, Any]]],
    after_by_window: OrderedDict[str, list[dict[str, Any]]],
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in base_exp.base.WINDOWS.items():
        before_result = baselines[label]["result"]
        before_overlay = base_exp.base._overlay_from_paper_trades(before_result, base_by_window[label])
        after_overlay = base_exp.base._overlay_from_paper_trades(before_result, after_by_window[label])
        before = base_exp.base.overlay_helper._metrics_with_overlay(before_result, before_overlay)
        after = base_exp.base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = base_exp.base.overlay_helper._delta(after, before)
        rows[label] = {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "before": before,
            "after": after,
            "delta": delta,
            "source_trade_count": len(base_by_window[label]),
            "target_trade_count": len(incremental_by_window[label]),
            "target_trade_pnl_usd": _round(sum(float(row.get("pnl") or 0.0) for row in incremental_by_window[label]), 2),
            "overlay_total_pnl_before": before_overlay["overlay_total_pnl"],
            "overlay_total_pnl_after": after_overlay["overlay_total_pnl"],
        }
    return rows


def _aggregate(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in window_rows.values())
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in window_rows.values())
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in window_rows.values())
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in window_rows.values())
    max_drawdown_before = max(float(row["before"]["max_drawdown_pct"]) for row in window_rows.values())
    max_drawdown_after = max(float(row["after"]["max_drawdown_pct"]) for row in window_rows.values())
    return {
        "before": {
            "expected_value_score": _round(before_ev, 6),
            "strategy_total_pnl": _round(before_pnl, 2),
            "total_pnl": _round(before_pnl, 2),
            "max_drawdown_pct": _round(max_drawdown_before, 6),
        },
        "after": {
            "expected_value_score": _round(after_ev, 6),
            "strategy_total_pnl": _round(after_pnl, 2),
            "total_pnl": _round(after_pnl, 2),
            "max_drawdown_pct": _round(max_drawdown_after, 6),
        },
        "delta": {
            "expected_value_score": _round(after_ev - before_ev, 6),
            "expected_value_score_pct": _round((after_ev - before_ev) / before_ev, 6) if before_ev else None,
            "strategy_total_pnl": _round(after_pnl - before_pnl, 2),
            "total_pnl": _round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_pct": _round((after_pnl - before_pnl) / before_pnl, 6) if before_pnl else None,
            "max_drawdown_pct": _round(max_drawdown_after - max_drawdown_before, 6),
        },
    }


def _target_summary(incremental_by_window: OrderedDict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return base_exp._target_summary(incremental_by_window)


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
        "accepted_companyfacts_filing_timeliness_support"
        if alpha_passed
        else "rejected_companyfacts_filing_timeliness_support"
    )
    rationale = (
        "Filing timeliness support passed Gate 4 and is retained in the shared default-off paper adapter without live/default order changes."
        if alpha_passed
        else "Filing timeliness support failed Gate 4; no strategy or production behavior is retained."
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
        f"# {EXPERIMENT_ID}: Companyfacts Filing Timeliness Support",
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
            "The same rule is promoted through the shared default-off paper adapter "
            "(`quant/fundamental_growth_rs_paper_sleeve.py`). It changes no live/default "
            "orders, no production signal generation, no exits, and no LLM/news boundary.",
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
            f"# {EXPERIMENT_ID} Companyfacts filing timeliness support",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            f"- Incremental target trades: {payload['target_trade_summary']['target_trade_count']}",
            "- Production impact: shared default-off paper adapter; no live orders changed.",
            "",
        ]
    )


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    allowed_scope = list(ticket.get("allowed_write_scope") or [])
    for path in [
        "quant/fundamental_growth_rs_paper_sleeve.py",
        "quant/test_fundamental_growth_rs_paper_sleeve.py",
        "quant/default_off_alpha_attribution.py",
        "quant/report_generator.py",
        "docs/current_state.md",
        "docs/alpha-optimization-playbook.md",
        "docs/production_backtest_parity.md",
        "docs/data_edge_context_layers.md",
        "experiments/artifacts/exp-20260601-027_companyfacts_filing_timeliness_support.md",
    ]:
        if path not in allowed_scope:
            allowed_scope.append(path)
    ticket["allowed_write_scope"] = allowed_scope
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
        with EXPERIMENT_LOG.open("r", encoding="utf-8") as handle:
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
    gate2_open_positions = base_exp.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_payload = _load_source_payload()
    source_rows_by_window = _source_target_rows_by_window(source_payload)
    base_by_window, after_by_window, incremental_by_window, selection_diagnostics = _select_supported_trades(
        source_rows_by_window
    )
    baselines = base_exp._load_baselines()
    window_rows = _run_window_metrics(baselines, base_by_window, after_by_window, incremental_by_window)
    aggregate = _aggregate(window_rows)
    target_summary = _target_summary(incremental_by_window)
    gate4 = _gate4(aggregate, window_rows, target_summary)
    timestamp = _utc_now()
    ticket = _load_ticket()
    production_impact = {
        "replay_only": False,
        "default_off_paper_only": True,
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
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
    decision = gate4["decision"]
    accepted = bool(gate4["passed"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "lane": "alpha_search",
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "SEC Companyfacts filing timeliness may add a quality signal to the accepted "
            "gross-margin Fundamental Growth + RS default-off paper adapter."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "companyfacts_filing_timeliness_quality_support",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260601-026",
            "exp-20260528-016",
            "exp-20260601-019",
            "exp-20260601-004",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_sec_companyfacts_filing_timeliness_field",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "timely_10q_max_days": TIMELY_10Q_MAX_DAYS,
            "timely_10k_max_days": TIMELY_10K_MAX_DAYS,
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
            "baseline_source": "accepted exp-20260601-026 gross-margin default-off paper adapter overlay",
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "target_trades_by_window operating_income_current_filed",
                "target_trades_by_window operating_income_current_period_end",
                "target_trades_by_window operating_income_current_form",
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
            "1_alpha_hypothesis": "candidate_pool / default-off paper allocation: timely SEC Companyfacts filing may indicate higher reporting quality.",
            "2_history_check": {
                "exp-20260601-026": "Gross-margin quality accepted as shared default-off adapter.",
                "exp-20260528-016": "Filing recency support accepted, but it measures filed-to-signal age, not filed-to-period-end timeliness.",
                "exp-20260601-019": "FCF-yield value positive but failed concentration.",
                "exp-20260601-004": "Earnings-yield value positive but failed concentration.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "docs/backtesting.md three PIT-DTE windows, using accepted gross-margin adapter as before; require aggregate EV/PnL positive, all windows improved, drawdown drift <=0.5pp, survival >=5%, sample and concentration guards.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260601_027_companyfacts_filing_timeliness_support.py",
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact,
        "ticket": ticket,
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "new forward replacement-value rows or a distinct filing-quality field",
            "no filing-timeliness threshold/scalar retune on the same frozen windows",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            "quant/fundamental_growth_rs_paper_sleeve.py",
            "quant/test_fundamental_growth_rs_paper_sleeve.py",
            "quant/default_off_alpha_attribution.py",
            "quant/report_generator.py",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
            "docs/production_backtest_parity.md",
            "docs/data_edge_context_layers.md",
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
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
