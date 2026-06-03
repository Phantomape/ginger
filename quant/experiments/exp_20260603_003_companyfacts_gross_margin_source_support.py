"""exp-20260603-003: Companyfacts gross-margin source support scout.

Replay-only alpha check. It tests whether already-selected Companyfacts
Fundamental Growth + RS paper rows whose gross margin is reconstructed from a
PIT SEC cost_of_revenue fallback deserve a small default-off paper support
scalar. It does not alter live orders, shared adapters, ranking, sizing, exits,
LLM, or news behavior.
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

from quant.experiments import exp_20260602_009_companyfacts_sector_residual_support as sector_exp  # noqa: E402


EXPERIMENT_ID = "exp-20260603-003"
STEM = "companyfacts_gross_margin_source_support"
TRIAL_FAMILY = "companyfacts_gross_margin_source_provenance"
CHANGED_VARIABLE = "gross_margin_cost_fallback_support_v1"
RULE_VERSION = CHANGED_VARIABLE

SUPPORT_SCALAR = 1.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_003_{STEM}.json"
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


def _gross_margin_source_context(row: dict[str, Any]) -> dict[str, Any]:
    gross_profit_form = str(row.get("gross_profit_form") or "").strip()
    cost_filed = str(row.get("cost_of_revenue_filed") or "").strip()
    cost_form = str(row.get("cost_of_revenue_form") or "").strip()
    direct_gross_profit = bool(gross_profit_form)
    cost_fallback = bool(cost_filed) and not direct_gross_profit
    if cost_fallback:
        status = "cost_of_revenue_fallback"
    elif direct_gross_profit:
        status = "direct_gross_profit"
    elif cost_filed:
        status = "cost_of_revenue_with_direct_override"
    else:
        status = "missing_margin_source"
    return {
        "companyfacts_gross_margin_source_rule_version": RULE_VERSION,
        "companyfacts_gross_margin_source_known_at": (
            "accepted Companyfacts paper row fields derived from SEC facts with filed <= signal_date"
        ),
        "companyfacts_gross_margin_source_trade_enabled": False,
        "companyfacts_gross_margin_source_alters_orders": False,
        "companyfacts_gross_margin_source_status": status,
        "companyfacts_gross_margin_cost_fallback_pass_v1": cost_fallback,
        "companyfacts_gross_margin_source_support_scalar": SUPPORT_SCALAR if cost_fallback else 1.0,
        "gross_profit_form": gross_profit_form or None,
        "gross_profit_filed": row.get("gross_profit_filed"),
        "cost_of_revenue_form": cost_form or None,
        "cost_of_revenue_filed": row.get("cost_of_revenue_filed"),
        "gross_margin_status": row.get("gross_margin_status"),
        "gross_margin": row.get("gross_margin"),
    }


def _select_supported_trades() -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    _sector_before, sector_after, _sector_incremental, sector_diagnostics = sector_exp._select_supported_trades()

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
            context = _gross_margin_source_context(row)
            status = str(context.get("companyfacts_gross_margin_source_status") or "unknown")
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
                "pnl_without_companyfacts_gross_margin_source_support": _round(base_pnl, 2),
                "paper_pnl_source": "pnl_with_sector_residual_without_gross_margin_source_support",
                "trade_enabled": False,
                "alters_orders": False,
            }
            scalar = SUPPORT_SCALAR if context["companyfacts_gross_margin_cost_fallback_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_gross_margin_source_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["companyfacts_gross_margin_cost_fallback_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental = {
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "companyfacts_gross_margin_source_incremental_support",
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
        "supported_trade_count_by_window": supported_counts,
        "gross_margin_source_status_counts_by_window": status_counts,
        "supported_trade_sample_by_window": supported_samples,
        "blocked_prior_direction": {
            "experiment_id": "exp-20260603-002",
            "reason": "amended-form fields had zero selected-row coverage across the accepted Companyfacts stack",
        },
    }
    return before_by_window, after_by_window, incremental_by_window, diagnostics


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    ev_windows = [
        label
        for label, row in window_rows.items()
        if float(row["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_windows = [
        label
        for label, row in window_rows.items()
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
    passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if passed
        else "rejected_companyfacts_gross_margin_source_support"
    )
    rationale = (
        "Cost-of-revenue fallback source support passed the three-window alpha gate as a replay-only lead; a shared default-off adapter and parity tests are required before retention."
        if passed
        else "Cost-of-revenue fallback source support failed Gate 4; no production, shared adapter, or strategy behavior is retained."
    )
    return {
        "passed": passed,
        "alpha_passed": passed,
        "promotable_now": False,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_shared_adapter_before_promotion": passed,
        "requires_parity_before_promotion": passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Gross-Margin Source Support",
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
            "## Source Coverage",
            "",
            "```json",
            json.dumps(
                payload["selection_diagnostics"]["gross_margin_source_status_counts_by_window"],
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Production Parity",
            "",
            "Replay-only and default-off paper only. The test uses fields already emitted by the "
            "accepted Companyfacts paper route from SEC facts with `filed <= signal_date`. No live "
            "orders, shared production adapter, core ranking, sizing, exits, LLM, or news behavior changed.",
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
            f"# {EXPERIMENT_ID} Companyfacts gross-margin source support",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            f"- Incremental target trades: {payload['target_trade_summary']['target_trade_count']}",
            "- Production impact: replay-only default-off paper; no live orders changed.",
            "",
        ]
    )


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload["ticket"])
    allowed = list(ticket.get("allowed_write_scope") or [])
    for path in [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(BEFORE_JSON),
        _repo_rel(AFTER_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(CARD_MD),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
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
    accepted = bool(gate4["alpha_passed"] and gate4["promotable_now"])
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
            "Accepted Companyfacts Fundamental Growth + RS paper candidates whose gross-margin quality "
            "is reconstructed from PIT SEC cost_of_revenue fallback, rather than directly reported "
            "gross_profit, may have better allocation quality as a free-data disclosure/source-provenance edge."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "companyfacts_disclosure_quality_support",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260601-026",
            "exp-20260602-010",
            "exp-20260603-002",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_sec_companyfacts_gross_margin_source_provenance_field",
        "parameters": {
            "source_before_state": "accepted Companyfacts gross-margin + filing-timeliness + cost-liquidity + sector-residual paper stack",
            "source_experiment_id": "exp-20260602-010",
            "source_replay_helper": "quant/experiments/exp_20260602_009_companyfacts_sector_residual_support.py",
            "support_scalar": SUPPORT_SCALAR,
            "supported_status": "cost_of_revenue_fallback",
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
                "accepted Companyfacts paper rows ticker/signal_date/pnl",
                "accepted Companyfacts paper rows gross_profit_form/gross_profit_filed",
                "accepted Companyfacts paper rows cost_of_revenue_filed",
            ],
            "note": (
                "The tested source-provenance field is read from accepted Companyfacts paper rows "
                "already generated from SEC facts with filed dates <= signal_date."
            ),
        },
        "gate3": {
            "passed": True,
            "candidate_pool_changed": False,
            "note": "No core filter, live entry rule, or paper candidate filter was added; only replay paper notional is scaled after selected candidate selection.",
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
            "1_alpha_hypothesis": (
                "capital allocation / candidate quality: a Companyfacts paper row whose high gross margin "
                "comes from cost_of_revenue fallback may deserve a small default-off paper support scalar."
            ),
            "2_history_check": {
                "exp-20260601-026": "Accepted gross-margin quality candidate source; this run does not retune the gross-margin threshold.",
                "exp-20260602-010": "Current accepted sector-residual support stack used as this run's before-state.",
                "exp-20260603-002": "Amended-form disclosure-quality idea was blocked by zero selected-row coverage.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three PIT-DTE windows; aggregate EV/PnL positive; all windows improve; "
                "drawdown drift <=0.5pp; survival >=5%; >=20 target trades in all three windows; concentration guards pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260603_003_companyfacts_gross_margin_source_support.py"
            ),
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
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
            "Skipped LLM soft-ranking because usable replay data remains sparse; skipped amended-form "
            "support after exp-20260603-002 found zero selected-row coverage; skipped nearby post-earnings, "
            "Form4, FINRA, VBB, state-surface, broad OHLCV, and consensus source-set retunes because recent "
            "logs/playbook mark those as rejected or requiring forward rows."
        ),
        "interpretation": gate4["rationale"],
        "next_evidence_needed": (
            "If positive, promote only through a shared default-off adapter plus parity tests. If rejected, "
            "do not retry nearby gross-margin source-provenance scalars on frozen windows without forward rows."
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
            "notes": payload["interpretation"],
        }
    )


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate_delta": payload["aggregate"]["delta"],
                "failed_gates": payload["gate4"]["failed_gates"],
                "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
                "production_impact": payload["production_impact"],
                "artifact": _repo_rel(ARTIFACT_MD),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
