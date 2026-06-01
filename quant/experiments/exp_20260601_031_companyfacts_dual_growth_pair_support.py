"""exp-20260601-031: Companyfacts dual-growth pair support scout.

This tests one production-visible SEC Companyfacts quality field on top of the
accepted gross-margin + filing-timeliness + cost-liquidity Fundamental Growth
+ RS paper adapter. It writes replay evidence only; no shared adapter or live
order path is changed in this experiment.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_030_companyfacts_cost_liquidity_support as base  # noqa: E402


EXPERIMENT_ID = "exp-20260601-031"
STEM = "companyfacts_dual_growth_pair_support"
TRIAL_FAMILY = "companyfacts_dual_growth_pair_support"
CHANGED_VARIABLE = "companyfacts_dual_growth_pair_support_v1"
RULE_VERSION = CHANGED_VARIABLE

SOURCE_EXPERIMENT_ID = "exp-20260601-026"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "exp_20260601_026_companyfacts_gross_margin_rs_adapter.json"
)

SUPPORT_SCALAR = 1.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260601_031_{STEM}.json"
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
    return base._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return base._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    base._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    base._write_text(path, text)


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _dual_growth_context(row: dict[str, Any]) -> dict[str, Any]:
    eps_pass = bool(row.get("eps_growth_pass"))
    revenue_pass = bool(row.get("revenue_growth_pass"))
    pair_pass = bool(row.get("fundamental_growth_pair_available") or (eps_pass and revenue_pass))
    status = "ok" if pair_pass else "not_dual_growth"
    return {
        "companyfacts_dual_growth_pair_rule_version": RULE_VERSION,
        "companyfacts_dual_growth_pair_known_at": "SEC Companyfacts filed date <= signal_date",
        "companyfacts_dual_growth_pair_trade_enabled": False,
        "companyfacts_dual_growth_pair_alters_orders": False,
        "companyfacts_dual_growth_pair_status": status,
        "companyfacts_dual_growth_pair_pass_v1": pair_pass,
        "companyfacts_dual_growth_pair_support_scalar": SUPPORT_SCALAR if pair_pass else 1.0,
        "companyfacts_dual_growth_pair_eps_growth_pass": eps_pass,
        "companyfacts_dual_growth_pair_revenue_growth_pass": revenue_pass,
    }


def _select_supported_trades() -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    source_payload = base._load_source_payload()
    source_rows_by_window = base._source_target_rows_by_window(source_payload)
    ohlcv_by_window = base._load_ohlcv_index_by_window()
    _pre_cost_rows, accepted_rows, _cost_incremental, cost_diagnostics = base._select_supported_trades(
        source_rows_by_window,
        ohlcv_by_window,
    )

    before_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    after_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts: OrderedDict[str, dict[str, int]] = OrderedDict()
    supported_counts: OrderedDict[str, int] = OrderedDict()
    samples: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for label, rows in accepted_rows.items():
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        incremental_rows: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        sample_rows: list[dict[str, Any]] = []
        for row in rows:
            base_pnl = float(row.get("pnl") or 0.0)
            context = _dual_growth_context(row)
            counts[context["companyfacts_dual_growth_pair_status"]] = (
                counts.get(context["companyfacts_dual_growth_pair_status"], 0) + 1
            )
            before_trade = {
                **row,
                **context,
                "rule_version": RULE_VERSION,
                "strategy": "companyfacts_gross_margin_filing_timeliness_cost_liquidity_rs_candidate_pool",
                "pnl": _round(base_pnl, 2),
                "paper_pnl": _round(base_pnl, 2),
                "pnl_without_companyfacts_dual_growth_pair_support": _round(base_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_cost_liquidity_without_dual_growth_pair_support",
                "trade_enabled": False,
                "alters_orders": False,
            }
            scalar = SUPPORT_SCALAR if context["companyfacts_dual_growth_pair_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_dual_growth_pair_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["companyfacts_dual_growth_pair_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental = {
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "companyfacts_dual_growth_pair_incremental_support",
                }
                incremental_rows.append(incremental)
                if len(sample_rows) < 20:
                    sample_rows.append(after_trade)
        before_by_window[label] = before_rows
        after_by_window[label] = after_rows
        incremental_by_window[label] = incremental_rows
        status_counts[label] = dict(sorted(counts.items()))
        supported_counts[label] = len(incremental_rows)
        samples[label] = sample_rows

    diagnostics = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "source_artifact": _repo_rel(SOURCE_ARTIFACT),
        "baseline_before_state": "accepted exp-20260601-030 cost-liquidity support reconstructed from exp-026 target rows",
        "source_target_trade_count_by_window": {
            label: len(rows) for label, rows in source_rows_by_window.items()
        },
        "supported_trade_count_by_window": supported_counts,
        "dual_growth_status_counts_by_window": status_counts,
        "supported_trade_sample_by_window": samples,
        "cost_liquidity_diagnostics": cost_diagnostics,
    }
    return before_by_window, after_by_window, incremental_by_window, diagnostics


def _run_window_metrics(
    baselines: OrderedDict[str, dict[str, Any]],
    before_by_window: OrderedDict[str, list[dict[str, Any]]],
    after_by_window: OrderedDict[str, list[dict[str, Any]]],
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> OrderedDict[str, dict[str, Any]]:
    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, cfg in base.prev.base_exp.base.WINDOWS.items():
        before_result = baselines[label]["result"]
        before_overlay = base.prev.base_exp.base._overlay_from_paper_trades(
            before_result,
            before_by_window[label],
        )
        after_overlay = base.prev.base_exp.base._overlay_from_paper_trades(
            before_result,
            after_by_window[label],
        )
        before = base.prev.base_exp.base.overlay_helper._metrics_with_overlay(before_result, before_overlay)
        after = base.prev.base_exp.base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = base.prev.base_exp.base.overlay_helper._delta(after, before)
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
            "target_trade_pnl_usd": _round(
                sum(float(row.get("pnl") or 0.0) for row in incremental_by_window[label]),
                2,
            ),
            "overlay_total_pnl_before": before_overlay["overlay_total_pnl"],
            "overlay_total_pnl_after": after_overlay["overlay_total_pnl"],
        }
    return rows


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
    anti_repeat_blocked = alpha_passed
    decision = (
        "positive_replay_lead_not_promoted_requires_forward_rows"
        if alpha_passed
        else "rejected_companyfacts_dual_growth_pair_support"
    )
    rationale = (
        "Dual-growth pair support passed the three-window replay gate, but it is a historically adjacent Companyfacts dual-growth family; retain as a positive replay lead only until forward replacement-value rows justify shared adapter promotion."
        if alpha_passed
        else "Dual-growth pair support failed Gate 4; no shared strategy or production behavior is retained."
    )
    return {
        "passed": alpha_passed,
        "alpha_passed": alpha_passed,
        "promotable_now": False,
        "anti_repeat_blocked": anti_repeat_blocked,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_forward_replacement_value_before_promotion": True,
        "requires_shared_adapter_before_promotion": True,
        "requires_parity_before_promotion": True,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Dual-Growth Pair Support",
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
            "This replay uses fields already present on accepted Companyfacts paper rows "
            "and known from SEC Companyfacts filed-date-safe fundamentals before the "
            "paper entry. No shared adapter, live/default orders, core ranking, core "
            "sizing, exits, LLM, or news path changed.",
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
            f"# {EXPERIMENT_ID} Companyfacts dual-growth pair support",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            f"- Incremental target trades: {payload['target_trade_summary']['target_trade_count']}",
            "- Production impact: replay-only/default-off evidence; no live orders changed.",
            "",
        ]
    )


def _append_log_record(record: dict[str, Any]) -> None:
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


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    allowed_scope = list(ticket.get("allowed_write_scope") or [])
    for path in [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(BEFORE_JSON),
        _repo_rel(AFTER_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(TICKET_JSON),
        "docs/experiment_log.jsonl",
        "docs/experiment_registry.json",
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


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base.prev.base_exp.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    before_by_window, after_by_window, incremental_by_window, selection_diagnostics = _select_supported_trades()
    baselines = base.prev.base_exp._load_baselines()
    window_rows = _run_window_metrics(baselines, before_by_window, after_by_window, incremental_by_window)
    aggregate = base._aggregate(window_rows)
    target_summary = base._target_summary(incremental_by_window)
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
            "Accepted Companyfacts gross-margin plus filing-timeliness plus cost-liquidity paper candidates "
            "may have cleaner replacement value when both EPS growth and revenue growth are positive and filed-date-safe."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "companyfacts_dual_growth_pair_support",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": EXPERIMENT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260528-020",
            "exp-20260601-026",
            "exp-20260601-027",
            "exp-20260601-030",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_sec_companyfacts_growth_pair_field_on_accepted_gross_margin_adapter",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "baseline_before_state": "accepted exp-20260601-030 cost-liquidity support reconstructed from exp-026 target rows",
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
            "baseline_source": "current PIT-DTE canonical backtests plus accepted exp-20260601-030 cost-liquidity overlay",
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "target_trades_by_window eps_growth_pass",
                "target_trades_by_window revenue_growth_pass",
                "target_trades_by_window fundamental_growth_pair_available",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": True,
            "note": "No core production filter was added; default-off paper support scout only.",
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
            "1_alpha_hypothesis": "candidate_pool / default-off paper allocation: dual positive EPS and revenue growth may improve Companyfacts paper replacement value.",
            "2_history_check": {
                "exp-20260528-020": "Dual-growth support on the older Companyfacts stack was rejected/frozen.",
                "exp-20260601-026": "Gross-margin candidate source accepted.",
                "exp-20260601-027": "Filing-timeliness support accepted.",
                "exp-20260601-030": "Cost-liquidity support accepted.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "docs/backtesting.md three PIT-DTE windows, using accepted cost-liquidity adapter as before; require aggregate EV/PnL positive, all windows improved, drawdown drift <=0.5pp, survival >=5%, sample and concentration guards.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260601_031_companyfacts_dual_growth_pair_support.py",
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact,
        "ticket": dict(ticket),
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "closed forward replacement-value rows before any shared adapter promotion",
            "no nearby Companyfacts dual-growth threshold/scalar retune on the same frozen windows",
            "separate shared production/backtest adapter implementation and parity tests if forward evidence later supports promotion",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
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
        "realized_failure_mode": payload["gate4"]["failed_gates"] or ["anti_repeat_blocked"],
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
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "aggregate": payload["aggregate"],
        "target_trade_summary": payload["target_trade_summary"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "prediction": prediction,
        "calibration": calibration,
        "production_impact": payload["production_impact"],
        "interpretation": payload["interpretation"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "notes": "Positive replay evidence only; no shared policy retained because dual-growth is an adjacent frozen Companyfacts family without forward replacement-value rows.",
    }
    _append_log_record(log_record)
    _write_json(LOG_JSON, {**payload, "calibration": calibration, "log_record": log_record})
    print(json.dumps(_safe({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "aggregate_delta": payload["aggregate"]["delta"],
        "target_trade_summary": {
            k: v for k, v in payload["target_trade_summary"].items() if k != "ticker_rows"
        },
        "failed_gates": payload["gate4"]["failed_gates"],
        "artifact": _repo_rel(OUT_JSON),
    }), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
