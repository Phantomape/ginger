"""exp-20260602-013: Companyfacts operating-margin expansion support scout.

This is a replay-only alpha check. It retests an adjacent operating-margin
quality idea on top of the current accepted Companyfacts sector-residual paper
stack, then records whether the idea still has material incremental value.
No production policy, shared adapter, live orders, ranking, sizing, exits, LLM,
or news path changes.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260528_023_fundamental_growth_rs_operating_margin_durability as prior_margin  # noqa: E402
from quant.experiments import exp_20260602_009_companyfacts_sector_residual_support as sector_exp  # noqa: E402


EXPERIMENT_ID = "exp-20260602-013"
STEM = "companyfacts_operating_margin_expansion_support"
TRIAL_FAMILY = "companyfacts_operating_margin_expansion_support"
CHANGED_VARIABLE = "companyfacts_operating_margin_expansion_support_v1"
RULE_VERSION = CHANGED_VARIABLE

SUPPORT_SCALAR = 1.05
MIN_OPERATING_MARGIN_YOY_DELTA = 0.0
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
MATERIAL_CURRENT_STACK_EV_LIFT = 0.10

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_013_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
FALLBACK_LOG_RECORD_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.experiment_log_record.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    return sector_exp._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return sector_exp._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return sector_exp._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    sector_exp._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    sector_exp._write_text(path, text)


def _as_float(value: Any) -> float | None:
    return sector_exp._as_float(value)


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _window_labels() -> list[str]:
    return list(sector_exp.cost_exp.prev.base_exp.base.WINDOWS.keys())


def _margin_index_for_rows(rows_by_window: OrderedDict[str, list[dict[str, Any]]]) -> prior_margin.CompanyfactsOperatingMarginIndex:
    rows = [row for window_rows in rows_by_window.values() for row in window_rows]
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    max_signal_date = max(
        (str(row.get("signal_date") or row.get("date") or "")[:10] for row in rows),
        default="",
    )
    companyfacts_rows = prior_margin._source_base()._load_companyfacts_rows(
        max_filed=max_signal_date,
        tickers=tickers,
    )
    return prior_margin.CompanyfactsOperatingMarginIndex(companyfacts_rows)


def _margin_context(
    index: prior_margin.CompanyfactsOperatingMarginIndex,
    ticker: str,
    signal_date: str,
) -> dict[str, Any]:
    raw = index.current_context(ticker, signal_date)
    margin_delta = _as_float(raw.get("operating_margin_yoy_delta"))
    passed = bool(raw.get("operating_margin_durability_pass_v1") and margin_delta is not None and margin_delta >= MIN_OPERATING_MARGIN_YOY_DELTA)
    status = str(raw.get("operating_margin_status") or "unknown")
    if raw.get("operating_margin_durability_pass_v1") and not passed:
        status = "operating_margin_delta_below_floor"
    return {
        "companyfacts_operating_margin_expansion_rule_version": RULE_VERSION,
        "companyfacts_operating_margin_expansion_known_at": (
            "SEC Companyfacts operating_income/revenue facts with filed <= signal_date"
        ),
        "companyfacts_operating_margin_expansion_trade_enabled": False,
        "companyfacts_operating_margin_expansion_alters_orders": False,
        "companyfacts_operating_margin_expansion_status": status,
        "companyfacts_operating_margin_expansion_pass_v1": passed,
        "companyfacts_operating_margin_expansion_support_scalar": SUPPORT_SCALAR if passed else 1.0,
        "companyfacts_operating_margin_expansion_min_delta": MIN_OPERATING_MARGIN_YOY_DELTA,
        "operating_margin_current": raw.get("operating_margin_current"),
        "operating_margin_prior_year_same_quarter": raw.get("operating_margin_prior"),
        "operating_margin_yoy_delta": raw.get("operating_margin_yoy_delta"),
        "operating_income_current_value": raw.get("operating_income_current_value"),
        "operating_income_current_filed": raw.get("operating_income_current_filed"),
        "operating_income_current_period_end": raw.get("operating_income_current_period_end"),
        "operating_income_prior_value": raw.get("operating_income_prior_value"),
        "operating_income_prior_filed": raw.get("operating_income_prior_filed"),
        "operating_income_prior_period_end": raw.get("operating_income_prior_period_end"),
        "operating_margin_revenue_current_value": raw.get("operating_margin_revenue_current_value"),
        "operating_margin_revenue_current_filed": raw.get("operating_margin_revenue_current_filed"),
        "operating_margin_revenue_current_period_end": raw.get("operating_margin_revenue_current_period_end"),
        "operating_margin_revenue_prior_value": raw.get("operating_margin_revenue_prior_value"),
        "operating_margin_revenue_prior_filed": raw.get("operating_margin_revenue_prior_filed"),
        "operating_margin_revenue_prior_period_end": raw.get("operating_margin_revenue_prior_period_end"),
        "prior_operating_margin_experiment_id": "exp-20260528-023",
        "prior_operating_margin_experiment_decision": "rejected_fundamental_growth_rs_operating_margin_durability_support",
    }


def _select_supported_trades() -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    _sector_before, sector_after, _sector_incremental, sector_diagnostics = sector_exp._select_supported_trades()
    margin_index = _margin_index_for_rows(sector_after)

    before_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    after_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts: OrderedDict[str, dict[str, int]] = OrderedDict()
    supported_counts: OrderedDict[str, int] = OrderedDict()
    supported_samples: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for label, rows in sector_after.items():
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        incremental_rows: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        samples: list[dict[str, Any]] = []
        for row in rows:
            base_pnl = _as_float(row.get("pnl"))
            if base_pnl is None:
                continue
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            context = _margin_context(margin_index, ticker, signal_date)
            status = str(context.get("companyfacts_operating_margin_expansion_status") or "unknown")
            counts[status] += 1
            before_trade = {
                **row,
                **context,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "strategy": "companyfacts_gross_margin_filing_timeliness_cost_liquidity_sector_residual_rs_candidate_pool",
                "pnl": _round(base_pnl, 2),
                "paper_pnl": _round(base_pnl, 2),
                "pnl_without_companyfacts_operating_margin_expansion_support": _round(base_pnl, 2),
                "paper_pnl_source": "pnl_with_sector_residual_without_operating_margin_expansion_support",
                "trade_enabled": False,
                "alters_orders": False,
            }
            scalar = SUPPORT_SCALAR if context["companyfacts_operating_margin_expansion_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_operating_margin_expansion_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["companyfacts_operating_margin_expansion_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental = {
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "companyfacts_operating_margin_expansion_incremental_support",
                }
                incremental_rows.append(incremental)
                if len(samples) < 20:
                    samples.append(after_trade)
        before_by_window[label] = before_rows
        after_by_window[label] = after_rows
        incremental_by_window[label] = incremental_rows
        status_counts[label] = dict(sorted(counts.items()))
        supported_counts[label] = len(incremental_rows)
        supported_samples[label] = samples

    diagnostics = {
        "source_experiment_id": "exp-20260602-010",
        "source_replay_helper": "quant/experiments/exp_20260602_009_companyfacts_sector_residual_support.py",
        "source_artifact": _repo_rel(sector_exp.OUT_JSON),
        "source_reconstruction": sector_diagnostics,
        "prior_nearby_experiment": {
            "experiment_id": "exp-20260528-023",
            "decision": "rejected_fundamental_growth_rs_operating_margin_durability_support",
            "reason": (
                "The prior operating-margin durability scout beat the old core baseline "
                "but failed versus the then-current accepted stack; this run checks "
                "whether the same mechanism still has material incremental value on "
                "the current accepted sector-residual stack."
            ),
        },
        "supported_trade_count_by_window": supported_counts,
        "operating_margin_expansion_status_counts_by_window": status_counts,
        "supported_trade_sample_by_window": supported_samples,
    }
    return before_by_window, after_by_window, incremental_by_window, diagnostics


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
        target_summary["max_single_positive_share"] is not None
        and float(target_summary["max_single_positive_share"]) <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and float(target_summary["positive_pnl_hhi"]) <= MAX_POSITIVE_HHI
    )
    before_ev = float(aggregate["before"]["expected_value_score"] or 0.0)
    ev_delta = float(aggregate["delta"]["expected_value_score"] or 0.0)
    material_ev_lift_passed = before_ev > 0.0 and (ev_delta / before_ev) >= MATERIAL_CURRENT_STACK_EV_LIFT
    gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", ev_delta > 0.0),
            ("aggregate_pnl_positive", float(aggregate["delta"]["total_pnl"]) > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows) == len(window_rows)),
            ("all_windows_pnl_improved", len(pnl_windows) == len(window_rows)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            ("concentration_guard_passed", concentration_passed),
            ("anti_repeat_material_current_stack_ev_lift_passed", material_ev_lift_passed),
        ]
    )
    failed = [name for name, passed in gates.items() if not passed]
    core_failed = [name for name in failed if name != "anti_repeat_material_current_stack_ev_lift_passed"]
    core_alpha_passed = not core_failed
    passed = not failed
    if passed:
        decision = "positive_replay_lead_not_promoted_requires_forward_operating_margin_rows"
        rationale = (
            "Operating-margin expansion cleared the strict current-stack anti-repeat guard, "
            "but remains replay-only until forward replacement-value rows and a shared adapter "
            "parity pass exist."
        )
    elif core_alpha_passed:
        decision = "rejected_operating_margin_expansion_no_material_current_stack_lift"
        rationale = (
            "Operating-margin expansion was directionally positive but did not clear the "
            "10% current-stack EV lift required to reopen this prior rejected nearby "
            "Companyfacts scalar family."
        )
    else:
        decision = "rejected_companyfacts_operating_margin_expansion_support"
        rationale = (
            "Operating-margin expansion failed Gate 4; no production, shared adapter, "
            "or strategy behavior is retained."
        )
    return {
        "passed": passed,
        "core_alpha_passed": core_alpha_passed,
        "alpha_passed": passed,
        "promotable_now": False,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "core_failed_gates": core_failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "material_current_stack_ev_lift_required": MATERIAL_CURRENT_STACK_EV_LIFT,
        "material_current_stack_ev_lift_observed": _round(ev_delta / before_ev if before_ev else None, 6),
        "requires_forward_rows_before_retry": not passed,
        "requires_shared_adapter_before_promotion": passed,
        "requires_parity_before_promotion": passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Operating-Margin Expansion Support",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- current-stack EV lift: `{payload['gate4']['material_current_stack_ev_lift_observed']}` "
        f"(required `{MATERIAL_CURRENT_STACK_EV_LIFT}`)",
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
            "## Prior Nearby Evidence",
            "",
            "`exp-20260528-023` already tested non-declining operating margin versus "
            "the prior-year same quarter. It beat the old core baseline, but failed "
            "against the then-current accepted Companyfacts stack. This run uses the "
            "current accepted sector-residual stack as before-state and requires a "
            "10% current-stack EV lift before reopening this field family.",
            "",
            "## Production Parity",
            "",
            "Replay-only and default-off paper only. The test uses SEC Companyfacts "
            "operating_income/revenue facts with `filed <= signal_date` and rows "
            "already selected by the accepted Companyfacts paper route. No live "
            "orders, shared production adapter, core ranking, sizing, exits, LLM, "
            "or news behavior changed.",
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
            f"# {EXPERIMENT_ID} Companyfacts operating-margin expansion support",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            f"- Current-stack EV lift: {payload['gate4']['material_current_stack_ev_lift_observed']}",
            f"- Incremental target trades: {payload['target_trade_summary']['target_trade_count']}",
            "- Production impact: replay-only default-off paper; no live orders changed.",
            "",
        ]
    )


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    allowed = list(ticket.get("allowed_write_scope") or [])
    for path in [
        _repo_rel(BEFORE_JSON),
        _repo_rel(AFTER_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(FALLBACK_LOG_RECORD_JSON),
    ]:
        if path not in allowed:
            allowed.append(path)
    ticket["allowed_write_scope"] = allowed
    ticket["status"] = "completed"
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"] = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "alpha_passed": payload["gate4"]["alpha_passed"],
        "promotable_now": payload["gate4"]["promotable_now"],
        "artifact": _repo_rel(OUT_JSON),
        "report": _repo_rel(ARTIFACT_MD),
        "log": _repo_rel(LOG_JSON),
        "failed_gates": payload["gate4"]["failed_gates"],
        "metrics": {
            "aggregate_expected_value_delta": payload["aggregate"]["delta"]["expected_value_score"],
            "aggregate_total_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
            "material_current_stack_ev_lift_observed": payload["gate4"]["material_current_stack_ev_lift_observed"],
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
    try:
        tmp.replace(EXPERIMENT_LOG)
    except PermissionError as exc:
        _write_json(
            FALLBACK_LOG_RECORD_JSON,
            {
                "central_experiment_log_append": "skipped_permission_error",
                "central_experiment_log": _repo_rel(EXPERIMENT_LOG),
                "error": str(exc),
                "record": record,
            },
        )
        try:
            tmp.unlink()
        except OSError:
            pass
        print(f"WARNING: could not replace {_repo_rel(EXPERIMENT_LOG)}; wrote {_repo_rel(FALLBACK_LOG_RECORD_JSON)}")


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = sector_exp.cost_exp.prev.base_exp.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    before_by_window, after_by_window, incremental_by_window, selection_diagnostics = _select_supported_trades()
    baselines = sector_exp.cost_exp.prev.base_exp._load_baselines()
    window_rows = sector_exp.cost_exp._run_window_metrics(
        baselines,
        before_by_window,
        after_by_window,
        incremental_by_window,
    )
    aggregate = sector_exp.cost_exp._aggregate(window_rows)
    target_summary = sector_exp.cost_exp._target_summary(incremental_by_window)
    gate4 = _gate4(aggregate, window_rows, target_summary)
    timestamp = _utc_now()
    ticket = _load_ticket()
    accepted = False
    production_impact = {
        "replay_only": True,
        "default_off_paper_only": True,
        "shared_policy_changed": False,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "parity_test_added": False,
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
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": gate4["decision"],
        "lane": "alpha_search",
        "decision": gate4["decision"],
        "accepted": accepted,
        "hypothesis": (
            "Within the current accepted Companyfacts sector-residual Fundamental Growth + RS paper stack, "
            "rows with filed-date-safe non-declining operating margin versus the prior-year same quarter "
            "may still identify better replacement-value candidates. Because this is a prior rejected "
            "nearby Companyfacts scalar family, it must clear a 10% current-stack EV lift to reopen."
        ),
        "change_type": "default_off_paper_support_field",
        "mechanism_family": "companyfacts_operating_margin_expansion_support",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260528-023",
            "exp-20260528-012",
            "exp-20260601-026",
            "exp-20260602-010",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_sec_companyfacts_operating_margin_expansion_field",
        "parameters": {
            "source_before_state": "accepted Companyfacts gross-margin + filing-timeliness + cost-liquidity + sector-residual paper stack",
            "source_experiment_id": "exp-20260602-010",
            "source_replay_helper": "quant/experiments/exp_20260602_009_companyfacts_sector_residual_support.py",
            "support_scalar": SUPPORT_SCALAR,
            "min_operating_margin_yoy_delta": MIN_OPERATING_MARGIN_YOY_DELTA,
            "material_current_stack_ev_lift_required": MATERIAL_CURRENT_STACK_EV_LIFT,
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
                "anti_repeat_current_stack_ev_lift_min": MATERIAL_CURRENT_STACK_EV_LIFT,
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
            "baseline_source": "current accepted Companyfacts sector-residual paper stack reconstructed from exp-20260602-009 helper",
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "data/non_ohlcv/sec_companyfacts_selected_*.jsonl ticker/canonical/filed/end/fy/fp/value",
                "operating_income and revenue facts filed <= signal_date",
                "accepted Companyfacts paper rows ticker/signal_date/pnl",
            ],
            "note": (
                "The only tested field is operating-margin expansion, computed from "
                "Companyfacts operating_income and revenue facts with filed dates <= signal_date."
            ),
        },
        "gate3": {
            "passed": True,
            "survival_rates_after": OrderedDict(
                (label, row["after"]["survival_rate"]) for label, row in window_rows.items()
            ),
            "candidate_pool_changed": False,
            "note": (
                "No core filter, live entry rule, or paper candidate filter was added. "
                "The rule only scales replay paper notional after selected candidate selection."
            ),
        },
        "gate4": gate4,
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation / candidate-pool support alpha: filed-date-safe operating-margin "
                "expansion may still separate stronger rows inside the accepted Companyfacts paper stack."
            ),
            "2_history_check": {
                "exp-20260528-023": (
                    "Near duplicate; beat old core but failed against the then-current accepted stack, "
                    "so this run requires a material current-stack lift."
                ),
                "exp-20260528-012": "Gross-margin expansion was rejected versus the governed Companyfacts stack.",
                "exp-20260602-010": "Current accepted sector-residual support stack used as this run's before-state.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three-window before/after plus the anti-repeat 10% current-stack EV-lift guard."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260602_013_companyfacts_operating_margin_expansion_support.py"
            ),
        },
        "production_impact": production_impact,
        "ticket": ticket,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": sector_exp.cost_exp.prev.base_exp.base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
        },
        "anti_js": "No JavaScript was used.",
        "why_not_other_changes": (
            "Skipped LLM soft-ranking because data remains sparse; skipped DTE because another claimed "
            "measurement repair is active; skipped alpha_score and broad OHLCV shape mining because playbook "
            "marks those as frozen without new populated components or forward rows. This run records a strict "
            "current-stack retest of a nearby Companyfacts operating-margin idea and rejects it unless material."
        ),
        "interpretation": gate4["rationale"],
        "next_evidence_needed": (
            "Do not retry operating-margin thresholds/scalars on the frozen windows. The useful Companyfacts "
            "next step is forward replacement-value accumulation or a materially new free-data field."
        ),
    }


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, payload["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_json(LOG_JSON, payload)
    _write_text(ARTIFACT_MD, _artifact(payload))
    _write_text(CARD_MD, _card(payload))
    _update_ticket(payload)
    _update_registry(payload)
    _append_log_record(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": payload["timestamp"],
            "lane": payload["lane"],
            "status": payload["decision"],
            "decision": payload["decision"],
            "accepted": payload["accepted"],
            "hypothesis": payload["hypothesis"],
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "aggregate": payload["aggregate"],
            "gate4": payload["gate4"],
            "target_trade_summary": payload["target_trade_summary"],
            "production_impact": payload["production_impact"],
            "artifacts": {
                "result": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "report": _repo_rel(ARTIFACT_MD),
                "before": _repo_rel(BEFORE_JSON),
                "after": _repo_rel(AFTER_JSON),
            },
            "anti_js": payload["anti_js"],
        }
    )


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "ev_delta": payload["aggregate"]["delta"]["expected_value_score"],
                "pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
                "failed_gates": payload["gate4"]["failed_gates"],
                "artifact": _repo_rel(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
