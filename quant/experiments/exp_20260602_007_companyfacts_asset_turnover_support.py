"""exp-20260602-007: Companyfacts asset-turnover support scout.

This replay tests one SEC Companyfacts capital-efficiency field on top of the
accepted gross-margin + filing-timeliness + cost-liquidity Fundamental Growth
+ RS paper route. It is replay-only unless later forward replacement-value rows
justify a shared adapter promotion.
"""

from __future__ import annotations

import hashlib
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


EXPERIMENT_ID = "exp-20260602-007"
STEM = "companyfacts_asset_turnover_support"
TRIAL_FAMILY = "companyfacts_asset_turnover_support"
CHANGED_VARIABLE = "companyfacts_asset_turnover_support_v1"
RULE_VERSION = CHANGED_VARIABLE

SUPPORT_SCALAR = 1.05
MIN_ANNUALIZED_ASSET_TURNOVER = 0.50
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

NON_OHLCV_DIR = ROOT / "data" / "non_ohlcv"
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_007_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
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


class AssetTurnoverIndex:
    def __init__(self, *, tickers: set[str]) -> None:
        ticker_set = {ticker.upper() for ticker in tickers}
        by_ticker: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: {"revenue": [], "assets": []}
        )
        for path in sorted(NON_OHLCV_DIR.glob("sec_companyfacts_selected_*.jsonl")):
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    canonical = str(row.get("canonical") or "")
                    if canonical not in {"revenue", "assets"}:
                        continue
                    ticker = str(row.get("ticker") or "").upper()
                    filed = str(row.get("filed") or "")[:10]
                    value = _as_float(row.get("value"))
                    duration_days = _as_int(row.get("duration_days"))
                    if ticker not in ticker_set or not filed or value is None:
                        continue
                    if canonical == "revenue":
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
        revenue_row = self._latest(ticker, "revenue", signal_date)
        assets_row = self._latest(ticker, "assets", signal_date)
        missing = [
            name
            for name, row in (("revenue", revenue_row), ("assets", assets_row))
            if row is None
        ]
        base_context = {
            "companyfacts_asset_turnover_rule_version": RULE_VERSION,
            "companyfacts_asset_turnover_known_at": "SEC Companyfacts filed date <= signal_date",
            "companyfacts_asset_turnover_trade_enabled": False,
            "companyfacts_asset_turnover_alters_orders": False,
            "companyfacts_asset_turnover_min_annualized": MIN_ANNUALIZED_ASSET_TURNOVER,
        }
        if missing:
            return {
                **base_context,
                "companyfacts_asset_turnover_status": "missing_" + "_and_".join(missing),
                "companyfacts_asset_turnover_available": False,
                "companyfacts_asset_turnover_pass_v1": False,
                "companyfacts_asset_turnover_support_scalar": 1.0,
            }
        assert revenue_row is not None
        assert assets_row is not None
        revenue = _as_float(revenue_row.get("value"))
        assets = _as_float(assets_row.get("value"))
        revenue_duration_days = _as_int(revenue_row.get("duration_days"))
        if (
            revenue is None
            or assets is None
            or revenue_duration_days is None
            or revenue <= 0.0
            or assets <= 0.0
            or revenue_duration_days <= 0
        ):
            status = "invalid_revenue_or_assets"
            ratio = None
            annualized_ratio = None
            passed = False
        else:
            ratio = revenue / assets
            annualized_ratio = ratio * (365.0 / revenue_duration_days)
            passed = annualized_ratio >= MIN_ANNUALIZED_ASSET_TURNOVER
            status = "ok" if passed else "asset_turnover_below_floor"
        same_period = bool(revenue_row.get("end") and revenue_row.get("end") == assets_row.get("end"))
        return {
            **base_context,
            "companyfacts_asset_turnover_status": status,
            "companyfacts_asset_turnover_available": annualized_ratio is not None,
            "companyfacts_asset_turnover_pass_v1": passed,
            "companyfacts_asset_turnover_support_scalar": SUPPORT_SCALAR if passed else 1.0,
            "asset_turnover_ratio": _round(ratio, 6),
            "annualized_asset_turnover_ratio": _round(annualized_ratio, 6),
            "asset_turnover_same_period_end": same_period,
            "revenue_value": _round(revenue, 2),
            "revenue_filed": revenue_row.get("filed"),
            "revenue_period_end": revenue_row.get("end"),
            "revenue_duration_days": revenue_row.get("duration_days"),
            "revenue_form": revenue_row.get("form"),
            "assets_value": _round(assets, 2),
            "assets_filed": assets_row.get("filed"),
            "assets_period_end": assets_row.get("end"),
            "assets_form": assets_row.get("form"),
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
    index = AssetTurnoverIndex(tickers=tickers)

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
            status = context["companyfacts_asset_turnover_status"]
            counts[status] = counts.get(status, 0) + 1
            before_trade = {
                **row,
                **context,
                "rule_version": RULE_VERSION,
                "strategy": "companyfacts_gross_margin_filing_timeliness_cost_liquidity_rs_candidate_pool",
                "pnl": _round(base_pnl, 2),
                "paper_pnl": _round(base_pnl, 2),
                "pnl_without_companyfacts_asset_turnover_support": _round(base_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_cost_liquidity_without_asset_turnover_support",
                "trade_enabled": False,
                "alters_orders": False,
            }
            scalar = SUPPORT_SCALAR if context["companyfacts_asset_turnover_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_asset_turnover_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["companyfacts_asset_turnover_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental = {
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "companyfacts_asset_turnover_incremental_support",
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
        "asset_turnover_supported_trade_count_by_window": supported_counts,
        "asset_turnover_status_counts_by_window": status_counts,
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
        else "rejected_companyfacts_asset_turnover_support"
    )
    rationale = (
        "Asset-turnover support passed the three-window replay gate, but it is a nearby Companyfacts support field and is not promoted without closed forward replacement-value rows and a shared adapter parity pass."
        if alpha_passed
        else "Asset-turnover support failed Gate 4; no shared strategy or production behavior is retained."
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
        f"# {EXPERIMENT_ID}: Companyfacts Asset-Turnover Support",
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
            f"# {EXPERIMENT_ID} Companyfacts asset-turnover support",
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
        _repo_rel(MANIFEST_JSON),
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
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["delta"]["total_pnl"]
            break
    registry["updated_at"] = payload["timestamp"]
    _write_json(REGISTRY_JSON, registry)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest() -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        ARTIFACT_MD,
        TICKET_JSON,
        MANIFEST_JSON,
    ]
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": _utc_now(),
        "files": {
            _repo_rel(path): {
                "exists": path.exists(),
                "sha256": _sha256(path),
            }
            for path in paths
        },
    }
    _write_json(MANIFEST_JSON, manifest)


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
        "accepted": False,
        "hypothesis": (
            "SEC Companyfacts asset turnover may identify more capital-efficient "
            "default-off Fundamental Growth + RS paper candidates than the accepted "
            "cost-liquidity adapter alone."
        ),
        "change_type": "default_off_paper_support_field",
        "mechanism_family": "companyfacts_capital_efficiency",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "annualized_revenue_to_assets_ge_0p50_support_v1",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260601-026",
            "exp-20260601-030",
            "exp-20260602-001",
            "exp-20260529-003",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_sec_companyfacts_revenue_to_assets_field",
        "prediction": ticket.get("prediction") or {},
        "parameters": {
            "baseline_before_state": "accepted exp-20260601-030 cost-liquidity support reconstructed from exp-026 target rows",
            "min_annualized_asset_turnover": MIN_ANNUALIZED_ASSET_TURNOVER,
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
        "selection_diagnostics": selection_diagnostics,
        "target_trade_summary": target_summary,
        "gate1_baseline": {
            "source": "docs/backtesting.md canonical three-window replay",
            "baseline_result": "current accepted core baseline through exp-20260602-003",
            "baseline_expected_value_score_sum": aggregate["before"]["expected_value_score"],
            "baseline_total_pnl": aggregate["before"]["total_pnl"],
        },
        "gate2": {
            "open_positions_field_audit": gate2_open_positions,
            "runtime_field_coverage": {
                "companyfacts_revenue": "SEC Companyfacts canonical revenue filed <= signal_date",
                "companyfacts_assets": "SEC Companyfacts canonical assets filed <= signal_date",
                "entry_date": "present in reconstructed target trades",
                "target_price": "audited through open_positions field check",
            },
        },
        "gate3": {
            "survival_rate_by_window": {
                label: row["after"].get("survival_rate")
                for label, row in window_rows.items()
            },
            "hard_floor": 0.05,
            "passed": all(float(row["after"].get("survival_rate") or 0.0) >= 0.05 for row in window_rows.values()),
            "note": "No live/core filter was added; this is replay-only default-off paper support.",
        },
        "gate4": gate4,
        "gate_questions": {
            "1_alpha_hypothesis": (
                "capital allocation / candidate quality: Companyfacts annualized revenue/assets >= 0.50 "
                "may identify capital-efficient Fundamental Growth + RS paper rows."
            ),
            "2_history_check": {
                "exp-20260601-026": "Accepted gross-margin candidate source; current source rows.",
                "exp-20260601-030": "Accepted cost-liquidity support; current baseline for this replay.",
                "exp-20260602-001": "Cash-conversion support was positive but not promoted without forward rows.",
                "asset_turnover_history": "No prior asset-turnover / revenue-assets Companyfacts support experiment found by rg.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "docs/backtesting.md canonical three windows; EV/PnL positive in all windows, drawdown/survival/sample/concentration guards pass.",
            "5_reproducibility": f".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260602_007_{STEM}.py",
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.prev.base_exp.base.WINDOWS,
            "execution_model": (
                "Uses accepted Companyfacts gross-margin + filing-timeliness + cost-liquidity "
                "paper target rows, then applies a replay-only 1.05x incremental support "
                "where revenue/assets annualized from filed-date-safe SEC Companyfacts is >= 0.50. "
                "Entry/exit dates, fills, hold days, and core behavior are unchanged."
            ),
            "replay_llm": False,
            "replay_news": False,
        },
        "production_impact": production_impact,
        "ticket": ticket,
        "anti_js": "No JavaScript was used.",
        "why_not_other_changes": (
            "Skipped SEC filing text quality because exp-20260602-006 target rows had no usable revenue/margin/FCF bucket coverage. "
            "Skipped consensus/capacity retunes because exp-20260601-028 already promoted the shared adapter and nearby gates are frozen. "
            "Skipped Form 4 and estimate revisions because the playbook marks them watchlist/data-limited. "
            "Skipped R&D intensity because selected Companyfacts data contains no research/development canonical field."
        ),
    }


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, payload["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _card(payload))
    _write_text(ARTIFACT_MD, _artifact(payload))
    _append_log_record(payload)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest()


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "aggregate_ev_delta": payload["aggregate"]["delta"]["expected_value_score"],
                    "aggregate_pnl_delta": payload["aggregate"]["delta"]["total_pnl"],
                    "target_trade_count": payload["target_trade_summary"]["target_trade_count"],
                    "failed_gates": payload["gate4"]["failed_gates"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
