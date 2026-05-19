"""exp-20260519-036: broad-market shared paper adapter promotion.

Alpha search follow-up to exp-20260519-035. The prior scout found a
three-window positive default-off broad-market leadership paper pool, but it
was research-only. This run keeps the accepted price_floor_40 profile fixed and
tests the single production variable: move the same candidate logic into a
shared production-visible paper sleeve.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260519-036"
EXPERIMENT_SLUG = "broad_market_shared_paper_adapter"
BASELINE_EXPERIMENT_ID = "exp-20260519-033"
PARENT_EXPERIMENT_ID = "exp-20260519-035"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as parent  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    RULE_VERSION,
    backtest_trade_from_feature,
    build_broad_market_feature,
    candidate_passes_profile,
    select_broad_market_features,
)


WINDOWS = parent.WINDOWS
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
PARENT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / PARENT_EXPERIMENT_ID
    / "broad_market_price_floor_candidate_pool_shadow.json"
)

PROFILE_CONFIG = {
    **DEFAULT_CONFIG,
    "ret20_excess_spy_min": 0.035,
    "ret60_min": 0.08,
    "near_high_60_min": 0.93,
    "volume_ratio_20_min": 1.00,
    "decision_close_price_min": 40.0,
    "paper_notional_usd": 7_500.0,
    "max_active_positions": 5,
    "daily_entry_slots": 3,
    "hold_days": 20,
}


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _simulate_window(
    *,
    label: str,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> dict[str, Any]:
    spec = WINDOWS[label]
    days = parent._trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    active: list[dict[str, str]] = []
    trades: list[dict[str, Any]] = []
    daily_counts: dict[str, int] = {}

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = int(PROFILE_CONFIG["max_active_positions"]) - len(active)
        if capacity <= 0:
            continue
        active_tickers = {row["ticker"] for row in active}
        features = []
        for ticker in candidate_tickers:
            if ticker in active_tickers:
                continue
            rows = prices.get(ticker) or []
            idx = (indexes.get(ticker) or {}).get(day)
            if idx is None:
                continue
            feature = build_broad_market_feature(
                ticker=ticker,
                rows=rows,
                idx=idx,
                spy_rows=spy_rows,
                spy_index=spy_index,
            )
            if feature and candidate_passes_profile(feature, PROFILE_CONFIG):
                features.append(feature)
        selected = select_broad_market_features(
            features,
            capacity=capacity,
            config=PROFILE_CONFIG,
        )
        for rank, feature in enumerate(selected, start=1):
            trade = backtest_trade_from_feature(
                feature=feature,
                prices_by_ticker=prices,
                window_end=spec["end"],
                rank=rank,
                config=PROFILE_CONFIG,
            )
            if trade is None:
                continue
            trade["window"] = label
            trades.append(trade)
            active.append({"ticker": trade["ticker"], "exit_date": trade["exit_date"]})
            active_tickers.add(trade["ticker"])
        daily_counts[day] = len(features)

    return {
        "window": label,
        "profile": "price_floor_40",
        "trades": trades,
        "candidate_signal_days": sum(1 for count in daily_counts.values() if count > 0),
        "candidate_signal_count": sum(daily_counts.values()),
        "max_daily_candidate_count": max(daily_counts.values()) if daily_counts else 0,
        "sample_daily_candidate_counts": dict(list(daily_counts.items())[:20]),
    }


def _variant_payload(
    *,
    baseline_metrics: dict[str, dict[str, Any]],
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label, spec in WINDOWS.items():
        scout = _simulate_window(
            label=label,
            candidate_tickers=candidate_tickers,
            prices=prices,
            indexes=indexes,
        )
        trades = scout["trades"]
        all_trades.extend(trades)
        event_curve = parent._event_equity_curve(
            trades=trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        after_metrics[label] = parent._metrics_from_overlay(
            baseline_metrics=baseline_metrics[label],
            event_curve=event_curve,
            event_trades=trades,
        )
        sleeve[label] = parent._window_sleeve_summary(trades, scout)

    aggregate_delta = parent._aggregate_delta(baseline_metrics, after_metrics)
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = parent._single_ticker_positive_share(all_trades)
    top5_share = parent._top5_positive_share(all_trades)
    sample_guard_passed = len(all_trades) >= parent.MIN_SELECTED_TRADES
    window_guard_passed = selected_windows >= parent.MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= parent.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= parent.MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = (
        aggregate_delta["max_drawdown_worse_max"] <= parent.MAX_DRAWDOWN_WORSE
    )
    gate4_passed = bool(
        aggregate_delta["aggregate_ev_delta"] > 0
        and aggregate_delta["aggregate_pnl_delta"] > 0
        and aggregate_delta["windows_ev_improved"] >= parent.MIN_EV_IMPROVED_WINDOWS
        and aggregate_delta["windows_ev_regressed"] == 0
        and aggregate_delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and window_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    return {
        "variant_name": "price_floor_40_shared_adapter",
        "variant_type": "shared_default_off_broad_market_paper_adapter",
        "profile": {
            key: PROFILE_CONFIG[key]
            for key in (
                "ret20_excess_spy_min",
                "ret60_min",
                "near_high_60_min",
                "volume_ratio_20_min",
                "decision_close_price_min",
                "paper_notional_usd",
                "max_active_positions",
                "daily_entry_slots",
                "hold_days",
            )
        },
        "after_metrics": after_metrics,
        "delta_metrics": aggregate_delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "selected_pnl": round(sum(float(row.get("pnl") or 0.0) for row in all_trades), 2),
        "selected_win_rate": round(
            sum(1 for row in all_trades if float(row.get("pnl") or 0.0) > 0)
            / len(all_trades),
            4,
        )
        if all_trades
        else None,
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": parent._event_risk(all_trades),
        "selected_trades_sample": parent._trade_rows(all_trades, limit=50),
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta": aggregate_delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": aggregate_delta["aggregate_pnl_delta"],
            "windows_ev_improved": aggregate_delta["windows_ev_improved"],
            "windows_ev_regressed": aggregate_delta["windows_ev_regressed"],
            "windows_pnl_improved": aggregate_delta["windows_pnl_improved"],
            "windows_pnl_regressed": aggregate_delta["windows_pnl_regressed"],
            "selected_trade_count": len(all_trades),
            "minimum_selected_trades": parent.MIN_SELECTED_TRADES,
            "sample_guard_passed": sample_guard_passed,
            "selected_windows": selected_windows,
            "minimum_selected_windows": parent.MIN_SELECTED_WINDOWS,
            "window_guard_passed": window_guard_passed,
            "single_ticker_positive_share": single_share,
            "max_single_ticker_positive_share": parent.MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "top5_positive_share": top5_share,
            "max_top5_positive_share": parent.MAX_TOP5_POSITIVE_SHARE,
            "concentration_guard_passed": concentration_guard_passed,
            "max_drawdown_worse_max": aggregate_delta["max_drawdown_worse_max"],
            "max_drawdown_worse_guardrail": parent.MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
        },
    }


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            key: value
            for key, value in row.items()
            if key != "combined_equity_curve"
        }
        for label, row in metrics.items()
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Shared Paper Adapter",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: move the fixed exp-20260519-035 price_floor_40 candidate logic into a shared default-off paper adapter.",
        "",
        "## Three-Window Evidence",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Broad Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        drow = delta["by_window"][label]
        sleeve = payload["broad_market_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(drow["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(drow["total_pnl"]),
                trades=sleeve["trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    gate2 = parent._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")
    baseline_payload = parent._json_load(parent.BASELINE_JSON)
    parent_payload = parent._json_load(PARENT_JSON)
    if parent_payload.get("decision") != "observed_promising_default_off_broad_market_price_floor_candidate_pool":
        raise RuntimeError(f"Unexpected parent decision: {parent_payload.get('decision')}")
    baseline_metrics = baseline_payload["after_metrics"]
    universe_state = parent._load_tradeable_universe()
    tradeable_universe = set(universe_state["excluded_tradeable_universe"])
    warehouse = parent._warehouse_audit()
    candidate_universe = parent._candidate_universe(tradeable_universe)
    prices = parent._load_price_rows(candidate_universe["tickers"])
    indexes = parent._index_by_date(prices)

    variant = _variant_payload(
        baseline_metrics=baseline_metrics,
        candidate_tickers=candidate_universe["tickers"],
        prices=prices,
        indexes=indexes,
    )
    delta = variant["delta_metrics"]
    parent_delta = parent_payload["delta_metrics"]
    parity = {
        "parent_experiment_id": PARENT_EXPERIMENT_ID,
        "parent_selected_variant": parent_payload["selected_variant"]["variant_name"],
        "shared_rule_version": RULE_VERSION,
        "aggregate_ev_delta_match": round(
            delta["aggregate_ev_delta"] - parent_delta["aggregate_ev_delta"],
            6,
        ),
        "aggregate_pnl_delta_match": round(
            delta["aggregate_pnl_delta"] - parent_delta["aggregate_pnl_delta"],
            2,
        ),
        "trade_count_match": variant["selected_trade_count"]
        - parent_payload["selected_variant"]["selected_trade_count"],
        "passed": (
            abs(delta["aggregate_ev_delta"] - parent_delta["aggregate_ev_delta"]) <= 0.0001
            and abs(delta["aggregate_pnl_delta"] - parent_delta["aggregate_pnl_delta"]) <= 0.01
            and variant["selected_trade_count"]
            == parent_payload["selected_variant"]["selected_trade_count"]
        ),
    }
    decision = (
        "accepted_default_off_broad_market_shared_paper_adapter"
        if variant["gate4"]["passed"] and parity["passed"]
        else "rejected_broad_market_shared_paper_adapter"
    )
    status = "accepted" if decision.startswith("accepted") else "rejected"
    gate3 = {
        "signals_generated": {
            label: baseline_metrics[label].get("signals_generated") for label in WINDOWS
        },
        "signals_survived": {
            label: baseline_metrics[label].get("signals_survived") for label in WINDOWS
        },
        "survival_rate": {
            label: baseline_metrics[label].get("survival_rate") for label in WINDOWS
        },
        "survival_rate_min": parent._aggregate(baseline_metrics)["survival_rate_min"],
        "passed": parent._aggregate(baseline_metrics)["survival_rate_min"] >= 0.05,
        "note": "No core filter was added; broad-market sleeve is default-off paper only.",
    }
    production_impact = {
        "shared_policy_changed": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "parity_test_added": True,
        "live_order_path_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "The exp-20260519-035 broad-market price-floor leadership pool "
            "should be promoted only as a shared default-off paper sleeve so "
            "future production runs can collect forward replacement-value "
            "evidence without changing live orders."
        ),
        "alpha_hypothesis": {
            "category": "entry / candidate_pool",
            "playbook_alignment": (
                "Matches all-market candidate discovery and sleeve governance; "
                "it avoids LLM soft-ranking and nearby state-surface retunes."
            ),
        },
        "history_check": {
            "nearby_experiments": [
                "exp-20260519-034 rejected broad-market leadership without price floor",
                "exp-20260519-035 observed price_floor_40 passed three-window Gate 4",
                "exp-20260519-033 latest accepted state-surface baseline",
            ],
            "anti_repeat": "No threshold or profile is changed from exp-20260519-035.",
        },
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": "broad_market_shared_paper_adapter_visibility",
        "single_causal_variable": (
            "production-visible shared paper adapter for fixed price_floor_40 "
            "broad-market leadership candidates"
        ),
        "component": "quant/broad_market_paper_sleeve.py",
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "parent_experiment_id": PARENT_EXPERIMENT_ID,
            "profile_config": variant["profile"],
            "candidate_count": candidate_universe["candidate_count"],
            "excluded_count": candidate_universe["excluded_count"],
            "locked_variables": [
                "core signal generation",
                "core entry filters",
                "core ranking",
                "core exits",
                "core sizing",
                "portfolio heat",
                "LLM/news decisions",
                "live/default orders",
                "price_floor_40 thresholds",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()},
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260519-033 baseline plus exp-20260519-035 price_floor_40 "
            "broad-market paper overlay recomputed through shared helper."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(parent.BASELINE_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": parent._aggregate(baseline_metrics),
            "known_measurement_boundary": (
                "Historical replay uses the exp-20260519-030 warehouse. "
                "Production adapter is default-off and records only when a "
                "paper universe feed is present."
            ),
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": variant["gate4"],
        "shared_adapter_parity": parity,
        "before_metrics": baseline_metrics,
        "after_metrics": variant["after_metrics"],
        "delta_metrics": delta,
        "aggregate_before": parent._aggregate(baseline_metrics),
        "aggregate_after": parent._aggregate(variant["after_metrics"]),
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"] for label in WINDOWS
        },
        "total_pnl_delta": {
            label: delta["by_window"][label]["total_pnl"] for label in WINDOWS
        },
        "broad_market_sleeve": variant["broad_market_sleeve"],
        "selected_variant": {
            "variant_name": variant["variant_name"],
            "selected_trade_count": variant["selected_trade_count"],
            "selected_ticker_count": variant["selected_ticker_count"],
            "selected_windows": variant["selected_windows"],
            "selected_pnl": variant["selected_pnl"],
            "selected_win_rate": variant["selected_win_rate"],
            "single_ticker_positive_share": variant["single_ticker_positive_share"],
            "top5_positive_share": variant["top5_positive_share"],
            "event_risk": variant["event_risk"],
            "selected_trades_sample": variant["selected_trades_sample"],
        },
        "candidate_universe": candidate_universe,
        "warehouse_audit": warehouse,
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts or decisions.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": "entry/candidate_pool: production-visible default-off paper adapter for high-price broad-market leadership candidates.",
            "2_past_similar_experiments": "exp-20260519-034 failed without price floor; exp-20260519-035 passed with price_floor_40 but lacked production adapter.",
            "3_single_variable": "Only shared paper adapter visibility changes; thresholds, hold, notional, slots, and universe controls stay fixed.",
            "4_acceptance": "Gate 4 must match exp035 three-window positive evidence and shared-adapter parity must pass.",
            "5_reproducibility": "Script, shared module, JSON artifact, log, ticket, markdown artifact, tests, and docs JSONL identify sources and metrics.",
        },
        "interpretation": (
            "Broad-market leadership remains a default-off paper alpha, not a "
            "core universe promotion. The useful step is forward paper "
            "replacement-value collection through shared code."
        ),
        "rejection_reason": None
        if decision.startswith("accepted")
        else "Shared adapter parity or Gate 4 failed.",
        "next_evidence_needed": (
            "Collect forward broad-market paper outcomes from the shared adapter; "
            "do not enable live orders until replacement value, tail shape, and "
            "candidate feed governance pass a separate gate."
        ),
        "why_not_other_changes": [
            "No nearby price-floor retune; exp035 already selected price_floor_40.",
            "No LLM soft-ranking; attribution sample remains sparse.",
            "No state-surface scalar mining; exp033 was just accepted.",
            "No core universe expansion; this is paper-only.",
        ],
        "known_risks": [
            "Historical replay depends on the large local exp-20260519-030 warehouse.",
            "Production adapter needs a maintained broad-market paper universe feed before daily candidates appear.",
            "Live promotion remains blocked by forward replacement-value and tail-concentration evidence.",
        ],
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "shared_module": "quant/broad_market_paper_sleeve.py",
            "shared_test": "quant/test_broad_market_paper_sleeve.py",
            "run_adapter": "quant/run.py",
            "report_adapter": "quant/report_generator.py",
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "baseline": _repo_rel(parent.BASELINE_JSON),
            "parent": _repo_rel(PARENT_JSON),
        },
    }
    return payload


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "shared_adapter_parity": payload["shared_adapter_parity"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "related_files": payload["related_files"],
    }


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "gate4": payload["gate4"],
        "shared_adapter_parity": payload["shared_adapter_parity"],
        "production_impact": payload["production_impact"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "gate4": payload["gate4"],
                    "shared_adapter_parity": payload["shared_adapter_parity"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "output": payload["related_files"]["output"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
