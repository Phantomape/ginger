"""exp-20260601-021: Companyfacts gross-margin + RS candidate-pool scout.

Replay-only alpha scout. It tests whether filed-date SEC Companyfacts gross
margin identifies better Fundamental Growth + RS paper candidates. It changes
no production orders, shared ranking, sizing, exits, or LLM decision boundary.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_002_companyfacts_share_contraction_rs_candidate_pool as base_exp  # noqa: E402


EXPERIMENT_ID = "exp-20260601-021"
STEM = "companyfacts_gross_margin_rs_candidate_pool"
TRIAL_FAMILY = "companyfacts_gross_margin_quality_candidate_pool"
CHANGED_VARIABLE = "gross_margin_quality_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

MIN_GROSS_MARGIN = 0.40
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260601_021_companyfacts_gross_margin_rs_candidate_pool.json"
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


def _as_int(value: Any) -> int | None:
    return base_exp._as_int(value)


class GrossMarginIndex:
    def __init__(self, *, tickers: set[str]) -> None:
        ticker_set = {ticker.upper() for ticker in tickers}
        by_ticker: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: {"revenue": [], "gross_profit": [], "cost_of_revenue": []}
        )
        for path in sorted(base_exp.NON_OHLCV_DIR.glob("sec_companyfacts_selected_*.jsonl")):
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    canonical = str(row.get("canonical") or "")
                    if canonical not in {"revenue", "gross_profit", "cost_of_revenue"}:
                        continue
                    ticker = str(row.get("ticker") or "").upper()
                    filed = str(row.get("filed") or "")[:10]
                    value = _as_float(row.get("value"))
                    duration_days = _as_int(row.get("duration_days"))
                    if ticker not in ticker_set or not filed or value is None:
                        continue
                    if duration_days is None or duration_days < 60 or duration_days > 400:
                        continue
                    by_ticker[ticker][canonical].append(
                        {
                            "ticker": ticker,
                            "canonical": canonical,
                            "filed": filed,
                            "value": value,
                            "duration_days": duration_days,
                            "end": row.get("end"),
                            "form": row.get("form"),
                            "fp": row.get("fp"),
                            "fy": row.get("fy"),
                            "concept": row.get("concept"),
                            "unit": row.get("unit"),
                        }
                    )
        for field_map in by_ticker.values():
            for rows in field_map.values():
                rows.sort(key=self._sort_key)
        self.by_ticker = by_ticker

    @staticmethod
    def _sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
        return (
            str(row.get("filed") or ""),
            str(row.get("end") or ""),
            int(row.get("duration_days") or 0),
            float(row.get("value") or 0.0),
        )

    def _latest(self, ticker: str, canonical: str, signal_date: str) -> dict[str, Any] | None:
        rows = [
            row
            for row in self.by_ticker.get(ticker.upper(), {}).get(canonical, [])
            if str(row.get("filed") or "") <= signal_date
        ]
        return rows[-1] if rows else None

    def context(self, ticker: str, signal_date: str) -> dict[str, Any]:
        revenue_row = self._latest(ticker, "revenue", signal_date)
        gross_row = self._latest(ticker, "gross_profit", signal_date)
        cost_row = self._latest(ticker, "cost_of_revenue", signal_date)
        if revenue_row is None:
            return {
                "gross_margin_status": "missing_revenue",
                "gross_margin_available": False,
                "known_at": "SEC Companyfacts filed date <= signal date",
            }

        revenue = _as_float(revenue_row.get("value"))
        if revenue is None or revenue <= 0.0:
            return {
                "gross_margin_status": "invalid_revenue",
                "gross_margin_available": False,
                "known_at": "SEC Companyfacts filed date <= signal date",
            }

        gross_profit = _as_float(gross_row.get("value")) if gross_row else None
        source = "gross_profit"
        if gross_profit is None and cost_row is not None:
            cost_of_revenue = _as_float(cost_row.get("value"))
            if cost_of_revenue is not None:
                gross_profit = revenue - abs(cost_of_revenue)
                source = "revenue_minus_cost_of_revenue"
        if gross_profit is None:
            return {
                "gross_margin_status": "missing_gross_profit_and_cost_of_revenue",
                "gross_margin_available": False,
                "revenue": _round(revenue, 2),
                "revenue_filed": revenue_row.get("filed"),
                "known_at": "SEC Companyfacts filed date <= signal date",
            }

        gross_margin = gross_profit / revenue
        return {
            "gross_margin_status": "ok" if gross_margin >= 0.0 else "negative_gross_margin",
            "gross_margin_available": True,
            "gross_margin_pass_v1": gross_margin >= MIN_GROSS_MARGIN,
            "gross_margin_threshold_min": MIN_GROSS_MARGIN,
            "gross_margin": _round(gross_margin, 6),
            "gross_profit": _round(gross_profit, 2),
            "gross_margin_source": source,
            "revenue": _round(revenue, 2),
            "revenue_filed": revenue_row.get("filed"),
            "revenue_period_end": revenue_row.get("end"),
            "revenue_duration_days": revenue_row.get("duration_days"),
            "revenue_form": revenue_row.get("form"),
            "gross_profit_filed": gross_row.get("filed") if gross_row else None,
            "gross_profit_period_end": gross_row.get("end") if gross_row else None,
            "gross_profit_duration_days": gross_row.get("duration_days") if gross_row else None,
            "gross_profit_form": gross_row.get("form") if gross_row else None,
            "cost_of_revenue_filed": cost_row.get("filed") if cost_row else None,
            "known_at": "SEC Companyfacts filed date <= signal date",
        }


def _select_target_trades(
    rows_by_window: OrderedDict[str, list[dict[str, Any]]],
    margin_index: GrossMarginIndex,
) -> tuple[OrderedDict[str, list[dict[str, Any]]], dict[str, Any]]:
    selected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts_by_window: OrderedDict[str, dict[str, int]] = OrderedDict()

    for label, rows in rows_by_window.items():
        selected: list[dict[str, Any]] = []
        filtered: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("date") or row.get("signal_date") or "")[:10]
            context = margin_index.context(ticker, signal_date)
            status_counts[str(context.get("gross_margin_status") or "unknown")] += 1
            candidate = {
                **row,
                **context,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "gross_margin_rule_version": RULE_VERSION,
                "strategy": STEM,
                "trade_enabled": False,
                "alters_orders": False,
                "source_experiment_id": base_exp.SOURCE_EXPERIMENT_ID,
                "source_artifact": _repo_rel(base_exp.SOURCE_ARTIFACT),
                "paper_pnl_source": "pnl_without_low_liability_support",
            }
            if context.get("gross_margin_pass_v1") is not True:
                filtered.append({**candidate, "filter_reason": "gross_margin_not_available_or_below_floor"})
                continue
            pnl = _as_float(row.get("pnl_without_low_liability_support"))
            if pnl is None:
                pnl = _as_float(row.get("pnl"))
                candidate["paper_pnl_source"] = "pnl"
            if pnl is None:
                filtered.append({**candidate, "filter_reason": "missing_paper_pnl"})
                continue
            selected.append({**candidate, "pnl": _round(pnl, 2), "paper_pnl": _round(pnl, 2)})

        selected_by_window[label] = selected
        filtered_by_window[label] = filtered[:200]
        status_counts_by_window[label] = dict(sorted(status_counts.items()))

    diagnostics = {
        "source_target_trade_count_by_window": {
            label: len(rows) for label, rows in rows_by_window.items()
        },
        "selected_gross_margin_trade_count_by_window": {
            label: len(rows) for label, rows in selected_by_window.items()
        },
        "gross_margin_status_counts_by_window": status_counts_by_window,
        "filtered_candidates_sample_by_window": filtered_by_window,
    }
    return selected_by_window, diagnostics


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    ev_delta = float(aggregate["before"]["expected_value_score"]) - CANONICAL_DOC_EV
    pnl_delta = float(aggregate["before"]["total_pnl"]) - CANONICAL_DOC_PNL
    matches = abs(ev_delta) <= 0.001 and abs(pnl_delta) <= 1.0
    return {
        "baseline_matches_docs": matches,
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_replay_ev": aggregate["before"]["expected_value_score"],
        "current_replay_pnl": aggregate["before"]["total_pnl"],
        "ev_delta_vs_docs": _round(ev_delta, 6),
        "pnl_delta_vs_docs": _round(pnl_delta, 2),
        "note": (
            "Current replay baseline differs from docs/backtesting.md accepted baseline; "
            "positive replay evidence cannot be retained or promoted until parity is resolved."
        )
        if not matches
        else "Current replay aggregate baseline matches docs/backtesting.md within tolerance.",
    }


def _gate4(
    aggregate: dict[str, Any],
    window_rows: OrderedDict[str, dict[str, Any]],
    target_summary: dict[str, Any],
    baseline_caveat: dict[str, Any],
) -> dict[str, Any]:
    ev_windows = [
        label for label, row in window_rows.items()
        if float(row["delta"].get("expected_value_score") or 0.0) > 0.0
    ]
    pnl_windows = [
        label for label, row in window_rows.items()
        if float(row["delta"].get("total_pnl") or 0.0) > 0.0
    ]
    max_drawdown_delta = max(
        float(row["delta"].get("max_drawdown_pct") or 0.0) for row in window_rows.values()
    )
    min_survival_rate = min(
        float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values()
    )
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for rows in target_summary["trades_by_window"].values() if rows > 0)
    concentration_passed = (
        float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
        and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI
    )
    alpha_gates = OrderedDict(
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
    gates = OrderedDict(alpha_gates)
    gates["baseline_matches_docs_for_retention"] = bool(baseline_caveat["baseline_matches_docs"])
    alpha_failed = [name for name, passed in alpha_gates.items() if not passed]
    failed = [name for name, passed in gates.items() if not passed]
    alpha_passed = not alpha_failed
    promotable_now = alpha_passed and bool(baseline_caveat["baseline_matches_docs"])
    if alpha_passed and not baseline_caveat["baseline_matches_docs"]:
        decision = "positive_replay_lead_not_promoted_baseline_mismatch"
        rationale = (
            "The gross-margin quality field passed alpha checks, but current replay "
            "baseline drift blocks retention or promotion."
        )
    elif alpha_passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_adapter"
        rationale = (
            "The gross-margin quality field passed alpha checks, but this run did not "
            "add a shared production/backtest default-off adapter."
        )
    else:
        decision = "rejected_companyfacts_gross_margin_rs_candidate_pool"
        rationale = "Gate 4 alpha checks failed; no strategy or production behavior is retained."
    return {
        "passed": promotable_now,
        "alpha_passed": alpha_passed,
        "promotable_now": promotable_now,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "alpha_failed_gates": alpha_failed,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_parity_before_promotion": alpha_passed and not baseline_caveat["baseline_matches_docs"],
        "requires_shared_adapter_before_promotion": alpha_passed,
    }


def _artifact(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    target = payload["target_trade_summary"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts Gross-Margin + RS Candidate Pool",
        "",
        f"- decision: `{payload['decision']}`",
        f"- aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` "
        f"({agg['delta']['expected_value_score']:+.4f})",
        f"- aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` "
        f"({agg['delta']['total_pnl']:+,.2f})",
        f"- target trades: `{target['target_trade_count']}`",
        f"- max single positive share: `{target['max_single_positive_share']}`",
        f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
        f"- failed gates: `{', '.join(payload['gate4']['failed_gates']) or 'none'}`",
        "",
        "## Three-Window Result",
        "",
        "| window | EV before | EV after | EV delta | PnL delta | target trades |",
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
            "## Conclusion",
            "",
            payload["gate4"]["rationale"],
            "",
            "This scout used only SEC Companyfacts rows filed on or before the signal date. "
            "It made no live/default order, ranking, sizing, exit, LLM, news, or watchlist change.",
            "",
            "## Baseline Caveat",
            "",
            payload["baseline_caveat"]["note"],
            "",
            "## Top Positive Contributors",
            "",
            "| ticker | trades | paper PnL | positive PnL share |",
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


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


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
    _write_json(REGISTRY_JSON, registry)


def _card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Companyfacts gross-margin RS scout",
            "",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: {payload['aggregate']['delta']['expected_value_score']:+.4f}",
            f"- Aggregate PnL delta: ${payload['aggregate']['delta']['total_pnl']:+,.2f}",
            f"- Target trades: {payload['target_trade_summary']['target_trade_count']}",
            f"- Baseline matches docs: {payload['baseline_caveat']['baseline_matches_docs']}",
            "",
            "See artifact for the three-window table and production/backtest caveat.",
            "",
        ]
    )


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base_exp.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source_payload = base_exp._load_source_payload()
    source_rows_by_window = base_exp._source_target_rows_by_window(source_payload)
    tickers = {
        str(row.get("ticker") or "").upper()
        for rows in source_rows_by_window.values()
        for row in rows
        if row.get("ticker")
    }
    margin_index = GrossMarginIndex(tickers=tickers)
    selected_by_window, selection_diagnostics = _select_target_trades(
        source_rows_by_window,
        margin_index,
    )
    baselines = base_exp._load_baselines()
    window_rows = base_exp._run_windows(baselines, selected_by_window)
    aggregate = base_exp._aggregate(window_rows)
    target_summary = base_exp._target_summary(selected_by_window)
    baseline_caveat = _baseline_caveat(aggregate)
    gate4 = _gate4(aggregate, window_rows, target_summary, baseline_caveat)
    timestamp = _utc_now()
    ticket = _load_ticket()
    decision = gate4["decision"]
    accepted = bool(gate4["promotable_now"])

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "SEC Companyfacts gross-margin quality may identify higher-quality "
            "growth+RS paper candidates without relying on LLM soft-ranking or noisy "
            "OHLCV pattern expansion."
        ),
        "change_type": "default_off_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "mechanism_family": "companyfacts_gross_margin_quality_candidate_pool",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260528-006",
            "exp-20260528-019",
            "exp-20260601-004",
            "exp-20260601-019",
            "exp-20260601-020",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_sec_companyfacts_gross_margin_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base_exp.base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Selected paper trades use already slippage-adjusted next-open entry "
                "and ten-trading-day exit PnL from the accepted Fundamental Growth + RS source."
            ),
        },
        "parameters": {
            "source_experiment_id": base_exp.SOURCE_EXPERIMENT_ID,
            "source_artifact": _repo_rel(base_exp.SOURCE_ARTIFACT),
            "min_gross_margin": MIN_GROSS_MARGIN,
            "gross_margin_source": "latest filed-date revenue and gross_profit, with revenue-cost_of_revenue fallback",
            "duration_days": "60..400",
            "paper_pnl_source": "pnl_without_low_liability_support",
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
                "baseline_matches_docs_for_retention": True,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry / candidate_pool: high gross margin plus accepted growth+RS "
                "may isolate higher-quality compounder candidates."
            ),
            "2_history_check": {
                "exp-20260528-006": "Cash-conversion quality was observed but not retained.",
                "exp-20260528-019": "Working-capital discipline support was rejected.",
                "exp-20260601-004": "Earnings-yield value failed concentration.",
                "exp-20260601-019": "FCF-yield value failed concentration and baseline retention.",
                "exp-20260601-020": "Consensus source-pair failed drawdown/concentration.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three windows; aggregate EV/PnL positive; "
                "all three windows improve; >=20 target trades across all windows; "
                "target trades in all three windows; drawdown drift <=0.5pp; survival "
                ">=5%; max single positive share <=0.50 and HHI <=0.30; documented/current "
                "baseline must match for retention."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260601_021_companyfacts_gross_margin_rs_candidate_pool.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_caveat": baseline_caveat,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "source target_trades_by_window entry_date",
                "source target_trades_by_window exit_date",
                "source pnl_without_low_liability_support",
                "SEC Companyfacts revenue filed <= signal_date",
                "SEC Companyfacts gross_profit or cost_of_revenue filed <= signal_date",
            ],
        },
        "gate3": {
            "passed": min(float(row["after"].get("survival_rate") or 0.0) for row in window_rows.values()) >= 0.05,
            "note": "No core production filter was added. Survival is inherited from canonical core replay plus default-off paper overlay.",
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
        "before_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
        "after_metrics": OrderedDict((label, row["after"]) for label, row in window_rows.items()),
        "delta_metrics": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
        "aggregate": aggregate,
        "baseline_caveat": baseline_caveat,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "target_trades_by_window": selected_by_window,
        "selection_diagnostics": selection_diagnostics,
        "production_impact": {
            "replay_only": True,
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
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "ticket": ticket,
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "clean current-vs-docs baseline/parity decision before any positive replay promotion",
            "shared live/backtest adapter before order impact",
            "forward replacement-value rows before nearby Companyfacts quality-field retries",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
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
            "baseline_caveat": payload["baseline_caveat"],
        },
    )
    _write_json(
        AFTER_JSON,
        {
            **payload["aggregate"]["after"],
            "windows": payload["after_metrics"],
            "experiment_id": EXPERIMENT_ID,
            "artifact_role": "after_aggregate",
            "baseline_caveat": payload["baseline_caveat"],
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
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
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
        "baseline_caveat": payload["baseline_caveat"],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }
    base_exp._upsert_jsonl(EXPERIMENT_LOG, log_record)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "baseline_caveat": payload["baseline_caveat"],
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
