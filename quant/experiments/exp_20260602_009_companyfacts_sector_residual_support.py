"""exp-20260602-009: Companyfacts sector-residual support scout.

This alpha search tests one public-classification plus OHLCV field on top of
the accepted default-off Fundamental Growth + RS paper route. It is replay-only:
no live orders, shared adapters, core ranking, sizing, exits, LLM, or news path
change.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant import broad_market_sector_map  # noqa: E402
from quant.experiments import exp_20260601_030_companyfacts_cost_liquidity_support as cost_exp  # noqa: E402


EXPERIMENT_ID = "exp-20260602-009"
STEM = "companyfacts_sector_residual_support"
TRIAL_FAMILY = "companyfacts_sector_residual_strength_support"
CHANGED_VARIABLE = "companyfacts_sector_residual_strength_support_v1"
RULE_VERSION = CHANGED_VARIABLE

RET20_EXCESS_SECTOR_MIN = 0.03
MIN_SECTOR_MEMBER_RETURNS = 5
SUPPORT_SCALAR = 1.05
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_009_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
SOURCE_RESULT_JSON = cost_exp.OUT_JSON


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe(value: Any) -> Any:
    return cost_exp._safe(value)


def _round(value: Any, digits: int = 4) -> Any:
    return cost_exp._round(value, digits)


def _repo_rel(path: Path | str) -> str:
    return cost_exp._repo_rel(path)


def _write_json(path: Path, payload: Any) -> None:
    cost_exp._write_json(path, payload)


def _write_text(path: Path, text: str) -> None:
    cost_exp._write_text(path, text)


def _as_float(value: Any) -> float | None:
    return cost_exp._as_float(value)


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    return json.loads(TICKET_JSON.read_text(encoding="utf-8"))


def _baseline_context(aggregate: dict[str, Any]) -> dict[str, Any]:
    stored = json.loads(SOURCE_RESULT_JSON.read_text(encoding="utf-8"))
    stored_after = stored["aggregate"]["after"]
    ev_delta = float(aggregate["before"]["expected_value_score"]) - float(
        stored_after["expected_value_score"]
    )
    pnl_delta = float(aggregate["before"]["total_pnl"]) - float(stored_after["total_pnl"])
    return {
        "before_state_description": (
            "accepted Companyfacts cost-liquidity overlay reconstructed on the "
            "current canonical core replay"
        ),
        "stored_source_artifact": _repo_rel(SOURCE_RESULT_JSON),
        "stored_source_after_expected_value_score": stored_after["expected_value_score"],
        "stored_source_after_total_pnl": stored_after["total_pnl"],
        "current_before_expected_value_score": aggregate["before"]["expected_value_score"],
        "current_before_total_pnl": aggregate["before"]["total_pnl"],
        "current_before_minus_stored_source_ev": _round(ev_delta, 6),
        "current_before_minus_stored_source_pnl": _round(pnl_delta, 2),
        "note": (
            "The current before-state is higher than the stored exp-20260601-030 "
            "artifact because the canonical core replay now includes the accepted "
            "exp-20260602-003 post-earnings continuation lift. The before/after "
            "comparison itself uses one code path and one three-window replay."
        ),
    }


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _value(row: dict[str, Any] | None, *names: str) -> float | None:
    if not row:
        return None
    for name in names:
        value = _as_float(row.get(name))
        if value is not None:
            return value
    return None


def _load_snapshot_series(snapshot_path: str) -> dict[str, list[dict[str, Any]]]:
    path = ROOT / snapshot_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("ohlcv") if isinstance(payload, dict) else payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (raw or {}).items():
        clean = [row for row in rows or [] if _date(row)]
        clean.sort(key=_date)
        out[str(ticker).upper()] = clean
    return out


class SectorResidualIndex:
    def __init__(
        self,
        snapshot: dict[str, list[dict[str, Any]]],
        sector_cache: dict[str, Any],
    ) -> None:
        self.snapshot = snapshot
        self.sector_cache = sector_cache
        self.row_index: dict[str, dict[str, int]] = {
            ticker: {_date(row): idx for idx, row in enumerate(rows)}
            for ticker, rows in snapshot.items()
        }
        self.lookup_cache: dict[str, dict[str, Any]] = {}
        self.ret20_cache: dict[tuple[str, str], float | None] = {}
        self.sector_returns_cache: dict[tuple[str, str], list[float]] = {}

    def lookup(self, ticker: str) -> dict[str, Any]:
        norm = str(ticker or "").upper()
        if norm not in self.lookup_cache:
            self.lookup_cache[norm] = broad_market_sector_map.lookup_sector(
                norm,
                self.sector_cache,
            )
        return self.lookup_cache[norm]

    def ret20(self, ticker: str, date: str) -> float | None:
        norm = str(ticker or "").upper()
        key = (norm, date)
        if key in self.ret20_cache:
            return self.ret20_cache[key]
        rows = self.snapshot.get(norm) or []
        idx = (self.row_index.get(norm) or {}).get(date)
        if idx is None or idx < 20:
            self.ret20_cache[key] = None
            return None
        current = _value(rows[idx], "Close", "close")
        prior = _value(rows[idx - 20], "Close", "close")
        if current is None or prior is None or prior <= 0.0:
            self.ret20_cache[key] = None
            return None
        ret = (current / prior) - 1.0
        self.ret20_cache[key] = ret
        return ret

    def sector_returns(self, sector: str, date: str) -> list[float]:
        key = (sector, date)
        if key in self.sector_returns_cache:
            return self.sector_returns_cache[key]
        values: list[float] = []
        for ticker in self.snapshot:
            lookup = self.lookup(ticker)
            if lookup.get("status") != broad_market_sector_map.OK_STATUS:
                continue
            if lookup.get("sector") != sector:
                continue
            ret = self.ret20(ticker, date)
            if ret is not None and math.isfinite(ret):
                values.append(float(ret))
        self.sector_returns_cache[key] = values
        return values

    def context(self, ticker: str, signal_date: str) -> dict[str, Any]:
        lookup = self.lookup(ticker)
        sector = lookup.get("sector")
        stock_ret20 = self.ret20(ticker, signal_date)
        base_context = {
            "companyfacts_sector_residual_rule_version": RULE_VERSION,
            "companyfacts_sector_residual_known_at": (
                "signal-day close plus persisted public sector cache; all "
                "returns are computed with Date <= signal_date"
            ),
            "companyfacts_sector_residual_trade_enabled": False,
            "companyfacts_sector_residual_alters_orders": False,
            "companyfacts_sector_residual_min_ret20_excess_sector": RET20_EXCESS_SECTOR_MIN,
            "companyfacts_sector_residual_min_sector_members": MIN_SECTOR_MEMBER_RETURNS,
            "sector_lookup_rule_version": lookup.get("rule_version"),
            "sector_lookup_source": lookup.get("source"),
            "sector_lookup_status": lookup.get("status"),
            "sector": sector,
            "industry": lookup.get("industry"),
        }
        if lookup.get("status") != broad_market_sector_map.OK_STATUS or not sector:
            return {
                **base_context,
                "companyfacts_sector_residual_status": "missing_sector",
                "companyfacts_sector_residual_pass_v1": False,
                "companyfacts_sector_residual_support_scalar": 1.0,
                "ret20_excess_sector": None,
                "sector_member_return_count": 0,
            }
        if stock_ret20 is None:
            return {
                **base_context,
                "companyfacts_sector_residual_status": "missing_stock_ret20",
                "companyfacts_sector_residual_pass_v1": False,
                "companyfacts_sector_residual_support_scalar": 1.0,
                "stock_ret20": None,
                "ret20_excess_sector": None,
                "sector_member_return_count": 0,
            }
        sector_values = self.sector_returns(str(sector), signal_date)
        if len(sector_values) < MIN_SECTOR_MEMBER_RETURNS:
            return {
                **base_context,
                "companyfacts_sector_residual_status": "insufficient_sector_members",
                "companyfacts_sector_residual_pass_v1": False,
                "companyfacts_sector_residual_support_scalar": 1.0,
                "stock_ret20": _round(stock_ret20, 6),
                "ret20_excess_sector": None,
                "sector_member_return_count": len(sector_values),
            }
        sector_median_ret20 = median(sector_values)
        excess = float(stock_ret20) - float(sector_median_ret20)
        passed = excess >= RET20_EXCESS_SECTOR_MIN
        return {
            **base_context,
            "companyfacts_sector_residual_status": "ok" if passed else "ret20_excess_sector_below_floor",
            "companyfacts_sector_residual_pass_v1": passed,
            "companyfacts_sector_residual_support_scalar": SUPPORT_SCALAR if passed else 1.0,
            "stock_ret20": _round(stock_ret20, 6),
            "sector_median_ret20": _round(sector_median_ret20, 6),
            "ret20_excess_sector": _round(excess, 6),
            "sector_member_return_count": len(sector_values),
        }


def _load_residual_indexes() -> OrderedDict[str, SectorResidualIndex]:
    sector_cache = broad_market_sector_map.load_cache()
    indexes: OrderedDict[str, SectorResidualIndex] = OrderedDict()
    for label, cfg in cost_exp.prev.base_exp.base.WINDOWS.items():
        indexes[label] = SectorResidualIndex(
            _load_snapshot_series(str(cfg["snapshot"])),
            sector_cache,
        )
    return indexes


def _select_supported_trades() -> tuple[
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    OrderedDict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    source_payload = cost_exp._load_source_payload()
    source_rows_by_window = cost_exp._source_target_rows_by_window(source_payload)
    ohlcv_by_window = cost_exp._load_ohlcv_index_by_window()
    _filing_rows, cost_rows, _cost_incremental, cost_diagnostics = cost_exp._select_supported_trades(
        source_rows_by_window,
        ohlcv_by_window,
    )
    residual_indexes = _load_residual_indexes()

    before_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    after_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    incremental_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    status_counts: OrderedDict[str, dict[str, int]] = OrderedDict()
    supported_counts: OrderedDict[str, int] = OrderedDict()
    supported_samples: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for label, rows in cost_rows.items():
        before_rows: list[dict[str, Any]] = []
        after_rows: list[dict[str, Any]] = []
        incremental_rows: list[dict[str, Any]] = []
        counts: Counter[str] = Counter()
        samples: list[dict[str, Any]] = []
        index = residual_indexes[label]
        for row in rows:
            base_pnl = _as_float(row.get("pnl"))
            if base_pnl is None:
                continue
            ticker = str(row.get("ticker") or "").upper()
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            context = index.context(ticker, signal_date)
            status = str(context.get("companyfacts_sector_residual_status") or "unknown")
            counts[status] += 1
            before_trade = {
                **row,
                **context,
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "rule_version": RULE_VERSION,
                "strategy": "companyfacts_gross_margin_filing_timeliness_cost_liquidity_rs_candidate_pool",
                "pnl": _round(base_pnl, 2),
                "paper_pnl": _round(base_pnl, 2),
                "pnl_without_companyfacts_sector_residual_support": _round(base_pnl, 2),
                "paper_pnl_source": "pnl_with_cost_liquidity_without_sector_residual_support",
                "trade_enabled": False,
                "alters_orders": False,
            }
            scalar = SUPPORT_SCALAR if context["companyfacts_sector_residual_pass_v1"] else 1.0
            after_pnl = base_pnl * scalar
            after_trade = {
                **before_trade,
                "pnl": _round(after_pnl, 2),
                "paper_pnl": _round(after_pnl, 2),
                "paper_pnl_source": "pnl_with_companyfacts_sector_residual_support",
            }
            before_rows.append(before_trade)
            after_rows.append(after_trade)
            if context["companyfacts_sector_residual_pass_v1"]:
                incremental_pnl = after_pnl - base_pnl
                incremental = {
                    **after_trade,
                    "pnl": _round(incremental_pnl, 2),
                    "paper_pnl": _round(incremental_pnl, 2),
                    "incremental_support_pnl": _round(incremental_pnl, 2),
                    "paper_pnl_source": "companyfacts_sector_residual_incremental_support",
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
        "source_experiment_id": "exp-20260601-030",
        "source_artifact": _repo_rel(cost_exp.OUT_JSON),
        "source_reconstruction": cost_diagnostics,
        "supported_trade_count_by_window": supported_counts,
        "sector_residual_status_counts_by_window": status_counts,
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
        else "rejected_companyfacts_sector_residual_support"
    )
    rationale = (
        "Sector-residual support passed the three-window alpha gate as a replay-only lead; a shared default-off adapter and parity tests are required before retention."
        if passed
        else "Sector-residual support failed Gate 4; no production, shared adapter, or strategy behavior is retained."
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
        f"# {EXPERIMENT_ID}: Companyfacts Sector-Residual Support",
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
            "## Baseline Context",
            "",
            payload["baseline_context"]["note"],
            "",
            "## Production Parity",
            "",
            "Replay-only and default-off paper only. The test uses the persisted "
            "`broad_market_sector_map` cache plus fixed OHLCV snapshots and rows "
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
            f"# {EXPERIMENT_ID} Companyfacts sector-residual support",
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


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = cost_exp.prev.base_exp.base._audit_open_positions()
    if not gate2_open_positions.get("passed"):
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    before_by_window, after_by_window, incremental_by_window, selection_diagnostics = _select_supported_trades()
    baselines = cost_exp.prev.base_exp._load_baselines()
    window_rows = cost_exp._run_window_metrics(
        baselines,
        before_by_window,
        after_by_window,
        incremental_by_window,
    )
    aggregate = cost_exp._aggregate(window_rows)
    target_summary = cost_exp._target_summary(incremental_by_window)
    baseline_context = _baseline_context(aggregate)
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
            "Accepted Fundamental Growth + RS paper rows with positive 20-day "
            "stock-vs-sector residual strength may have better allocation quality "
            "than sector-lagging rows, using only public sector classification and "
            "signal-day OHLCV."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "companyfacts_sector_residual_strength_support",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260525-916",
            "exp-20260525-038",
            "exp-20260601-030",
            "exp-20260602-001",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_public_sector_map_plus_signal_day_ohlcv_residual_strength",
        "parameters": {
            "source_experiment_id": "exp-20260601-030",
            "source_artifact": _repo_rel(cost_exp.OUT_JSON),
            "before_state": "accepted Companyfacts gross-margin + filing-timeliness + cost-liquidity paper overlay",
            "ret20_excess_sector_min": RET20_EXCESS_SECTOR_MIN,
            "min_sector_member_returns": MIN_SECTOR_MEMBER_RETURNS,
            "support_scalar": SUPPORT_SCALAR,
            "sector_map": _repo_rel(broad_market_sector_map.DEFAULT_CACHE_PATH),
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
        "baseline_context": baseline_context,
        "window_results": window_rows,
        "target_trade_summary": target_summary,
        "selection_diagnostics": selection_diagnostics,
        "gate1": {
            "passed": True,
            "baseline_source": "accepted exp-20260601-030 cost-liquidity overlay reconstructed from exp-026 target rows",
            "baseline_artifact": _repo_rel(BEFORE_JSON),
            "baseline_metrics": OrderedDict((label, row["before"]) for label, row in window_rows.items()),
            "baseline_context": baseline_context,
        },
        "gate2": {
            "passed": True,
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "target_trades_by_window signal_date",
                "target_trades_by_window ticker",
                "canonical OHLCV snapshot signal_date Close",
                "canonical OHLCV snapshot signal_date minus 20 trading-day Close",
                "data/reference/broad_market_sector_map.json sector",
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
            "1_alpha_hypothesis": (
                "risk allocation / candidate quality: a Companyfacts paper row "
                "that beats its public sector cohort by at least 3pp over 20 "
                "days may deserve a small default-off paper support scalar."
            ),
            "2_history_check": {
                "exp-20260525-916": (
                    "Standalone sector-leadership source had positive aggregate "
                    "EV/PnL but failed late_strong and drawdown; this run is "
                    "narrower and only supports already accepted Companyfacts rows."
                ),
                "exp-20260525-038": "Accepted the broad-market sector map as a read-only production-visible field.",
                "exp-20260601-030": "Accepted Companyfacts cost-liquidity support; this run uses it as before state.",
                "exp-20260602-001": "Cash-conversion support was positive but not promoted without forward rows.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "docs/backtesting.md three PIT-DTE windows; aggregate EV/PnL "
                "positive; all windows improve; drawdown drift <=0.5pp; survival "
                ">=5%; >=20 target trades in all three windows; concentration "
                "guards pass."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260602_009_companyfacts_sector_residual_support.py"
            ),
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": production_impact,
        "ticket": ticket,
        "interpretation": gate4["rationale"],
        "next_retry_requires": [
            "forward replacement-value rows or an exact same-day replacement test before retrying nearby sector residual thresholds",
            "shared default-off adapter plus parity tests before any positive replay can be retained",
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
            _repo_rel(broad_market_sector_map.DEFAULT_CACHE_PATH),
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
    print(
        json.dumps(
            _safe(
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
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
