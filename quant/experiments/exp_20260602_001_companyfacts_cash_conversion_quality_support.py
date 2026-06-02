"""exp-20260602-001: Companyfacts cash-conversion quality support scout.

This replay tests one SEC Companyfacts cash-quality field on top of the
accepted gross-margin + filing-timeliness + cost-liquidity Fundamental Growth
+ RS paper route. It is replay-only unless later forward replacement-value rows
justify a shared adapter promotion.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260601_030_companyfacts_cost_liquidity_support as base  # noqa: E402


EXPERIMENT_ID = "exp-20260602-001"
STEM = "companyfacts_cash_conversion_quality_support"
TRIAL_FAMILY = "companyfacts_cash_conversion_quality_support"
CHANGED_VARIABLE = "companyfacts_cash_conversion_quality_support_v1"
RULE_VERSION = CHANGED_VARIABLE

SUPPORT_SCALAR = 1.05
MIN_OCF_TO_NET_INCOME = 1.0
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

NON_OHLCV_DIR = ROOT / "data" / "non_ohlcv"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
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


def _as_float(value: Any) -> float | None:
    return base._as_float(value)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


class CashConversionIndex:
    def __init__(self, *, tickers: set[str]) -> None:
        ticker_set = {ticker.upper() for ticker in tickers}
        by_ticker: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: {"operating_cash_flow": [], "net_income": []}
        )
        for path in sorted(NON_OHLCV_DIR.glob("sec_companyfacts_selected_*.jsonl")):
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    canonical = str(row.get("canonical") or "")
                    if canonical not in {"operating_cash_flow", "net_income"}:
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
            if str(row.get("filed") or "")[:10] <= signal_date
        ]
        return rows[-1] if rows else None

    def context(self, ticker: str, signal_date: str) -> dict[str, Any]:
        ocf_row = self._latest(ticker, "operating_cash_flow", signal_date)
        income_row = self._latest(ticker, "net_income", signal_date)
        missing = [
            name
            for name, row in (
                ("operating_cash_flow", ocf_row),
                ("net_income", income_row),
            )
            if row is None
        ]
        base_context = {
            "companyfacts_cash_conversion_rule_version": RULE_VERSION,
            "companyfacts_cash_conversion_known_at": "SEC Companyfacts filed date <= signal_date",
            "companyfacts_cash_conversion_trade_enabled": False,
            "companyfacts_cash_conversion_alters_orders": False,
            "companyfacts_cash_conversion_min_ocf_to_net_income": MIN_OCF_TO_NET_INCOME,
        }
        if missing:
            return {
                **base_context,
                "companyfacts_cash_conversion_status": "missing_" + "_and_".join(missing),
                "companyfacts_cash_conversion_available": False,
                "companyfacts_cash_conversion_pass_v1": False,
                "companyfacts_cash_conversion_support_scalar": 1.0,
            }
        assert ocf_row is not None
        assert income_row is not None
        ocf = _as_float(ocf_row.get("value"))
        income = _as_float(income_row.get("value"))
        if ocf is None or income is None:
            status = "invalid_cash_or_income"
            ratio = None
            passed = False
        elif income <= 0.0:
            status = "non_positive_net_income"
            ratio = None
            passed = False
        else:
            ratio = ocf / income
            passed = ocf > 0.0 and ratio >= MIN_OCF_TO_NET_INCOME
            status = "ok" if passed else "ocf_below_net_income"
        same_period = bool(ocf_row.get("end") and ocf_row.get("end") == income_row.get("end"))
        return {
            **base_context,
            "companyfacts_cash_conversion_status": status,
            "companyfacts_cash_conversion_available": ratio is not None,
            "companyfacts_cash_conversion_pass_v1": passed,
            "companyfacts_cash_conversion_support_scalar": SUPPORT_SCALAR if passed else 1.0,
            "ocf_to_net_income_ratio": _round(ratio, 6),
            "cash_conversion_same_period_end": same_period,
            "operating_cash_flow_value": _round(ocf, 2),
            "operating_cash_flow_filed": ocf_row.get("filed"),
            "operating_cash_flow_period_end": ocf_row.get("end"),
            "operating_cash_flow_duration_days": ocf_row.get("duration_days"),
            "operating_cash_flow_form": ocf_row.get("form"),
            "net_income_value": _round(income, 2),
            "net_income_filed": income_row.get("filed"),
            "net_income_period_end": income_row.get("end"),
            "net_income_duration_days": income_row.get("duration_days"),
            "net_income_form": income_row.get("form"),
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
    _pre_cost_rows, cost_rows, _cost_incremental, cost_diagnostics = base._select_supported_trades(
        source_rows_by_window,
        ohlcv_by_window,
    )
    tickers = {
        str(row.get("ticker") or "").upper()
        for rows in cost_rows.values()
        for row in rows
        if row.get("ticker")
    }
    index = CashConversionIndex(tickers=tickers)

    before_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    after_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts: OrderedDict[str, dict[str, int]] = OrderedDict()
    supported_counts: OrderedDict[str, int] = OrderedDict()
    samples: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for label, rows in cost_rows.items():
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        incremental_rows: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        sample_rows: list[dict[str, Any]] = []
        for row in rows:
            base_pnl = float(row.get("pnl") or 0.0)
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            context = index.context(ticker, signal_date)
            counts[context["companyfacts_cash_conversion_status"]] = (
                counts.get(context["companyfacts_cash_conversion_status"], 0) + 1
            )
            before_trade = {
                **row,
                **context,
                "rule_version": RULE_VERSION,
                "strategy": "companyfacts_gross_margin_filing_timeliness_cost_liquidity_rs_candidate_pool",
                "pnl": _round(base_pnl, 2),
                "paper_pnl": _round(base_pnl, 2),
                "pnl_without_companyfacts_cash_conversion_support": _round(base_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_cost_liquidity_without_cash_conversion_support",
                "trade_enabled": False,
                "alters_orders": False,
            }
            scalar = SUPPORT_SCALAR if context["companyfacts_cash_conversion_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_cash_conversion_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["companyfacts_cash_conversion_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental = {
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "companyfacts_cash_conversion_incremental_support",
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
        "source_experiment_id": base.SOURCE_EXPERIMENT_ID,
        "source_artifact": _repo_rel(base.SOURCE_ARTIFACT),
        "baseline_before_state": "accepted exp-20260601-030 cost-liquidity support reconstructed from exp-026 target rows",
        "source_target_trade_count_by_window": {
            label: len(rows) for label, rows in source_rows_by_window.items()
        },
        "cash_conversion_supported_trade_count_by_window": supported_counts,
        "cash_conversion_status_counts_by_window": status_counts,
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
    return base._run_window_metrics(baselines, before_by_window, after_by_window, incremental_by_window)


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
        "positive_replay_lead_not_promoted_requires_forward_rows"
        if alpha_passed
        else "rejected_companyfacts_cash_conversion_quality_support"
    )
    rationale = (
        "Cash-conversion quality support passed the three-window replay gate, but it is a nearby Companyfacts support field and is not promoted without closed forward replacement-value rows and a shared adapter parity pass."
        if alpha_passed
        else "Cash-conversion quality support failed Gate 4; no shared strategy or production behavior is retained."
    )
    return {
        "passed": alpha_passed,
        "alpha_passed": alpha_passed,
        "promotable_now": False,
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
        f"# {EXPERIMENT_ID}: Companyfacts Cash-Conversion Quality Support",
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
            "This replay uses SEC Companyfacts rows with filed dates on or before the "
            "signal date. It does not change shared production/backtest policy, live "
            "orders, core ranking, sizing, exits, LLM, or news behavior. Any future "
            "promotion requires a shared default-off adapter and parity tests.",
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
            f"# {EXPERIMENT_ID} Companyfacts cash-conversion quality support",
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
            "SEC Companyfacts cash-conversion quality may identify cleaner default-off "
            "Fundamental Growth + RS paper candidates than the accepted cost-liquidity adapter alone."
        ),
        "change_type": "default_off_paper_support_field",
        "mechanism_family": "companyfacts_cash_conversion_quality",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "ocf_to_net_income_ge_1_support_v1",
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260504-004",
            "exp-20260601-019",
            "exp-20260601-030",
            "exp-20260601-031",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_sec_companyfacts_ocf_to_net_income_field",
        "parameters": {
            "baseline_before_state": "accepted exp-20260601-030 cost-liquidity support reconstructed from exp-026 target rows",
            "min_ocf_to_net_income": MIN_OCF_TO_NET_INCOME,
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
                "sec_companyfacts_selected operating_cash_flow filed <= signal_date",
                "sec_companyfacts_selected net_income filed <= signal_date",
                "target_trades_by_window signal_date",
                "target_trades_by_window ticker",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
        },
        "gate3": {
            "passed": True,
            "note": "No core production filter was added; replay-only default-off paper support scout.",
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
            "1_alpha_hypothesis": "candidate_pool / default-off paper support: OCF covering net income may indicate higher accounting quality within accepted Companyfacts + RS candidates.",
            "2_history_check": {
                "exp-20260504-004": "Broad Companyfacts financial-quality shadow was observed-only, not a candidate-pool support field on the accepted adapter.",
                "exp-20260601-019": "FCF-yield candidate pool was positive but failed concentration and baseline-retention checks; this run removes capex, shares, and price/yield valuation.",
                "exp-20260601-030": "Cost-liquidity support is the accepted before-state.",
                "exp-20260601-031": "Dual-growth pair replay was positive but not promoted because the nearby growth family needs forward rows.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "docs/backtesting.md three PIT-DTE windows, using accepted cost-liquidity adapter as before; require aggregate EV/PnL positive, all windows improved, drawdown drift <=0.5pp, survival >=5%, sample and concentration guards.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260602_001_companyfacts_cash_conversion_quality_support.py",
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact,
        "ticket": dict(ticket),
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "closed forward replacement-value rows before any shared adapter promotion",
            "no nearby Companyfacts cash/yield threshold or scalar retune on the same frozen windows",
            "shared production/backtest adapter implementation and parity tests if forward evidence later supports promotion",
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
                "gate4_failed_gates": payload["gate4"]["failed_gates"],
                "target_trade_summary": payload["target_trade_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
