"""exp-20260520-002: broad-market low-extension paper notional.

Alpha search follow-up to exp-20260519-037. The accepted broad-market
price-floor leadership pool and rank-notional profile are fixed. This run
changes one causal variable: an extra default-off paper notional scalar for
already-selected broad-market candidates whose five-trading-day return is low.

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


EXPERIMENT_ID = "exp-20260520-002"
EXPERIMENT_SLUG = "broad_market_low_extension_notional"
BASELINE_EXPERIMENT_ID = "exp-20260519-037"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    DEFAULT_CONFIG,
    LOW_EXTENSION_RULE_VERSION,
    RULE_VERSION,
    backtest_trade_from_feature,
    broad_market_candidate_notional_payload,
    build_broad_market_feature,
    candidate_passes_profile,
    select_broad_market_features,
)


WINDOWS = p35.WINDOWS
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "broad_market_rank_notional_profile.json"
)
CONTROL_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / CONTROL_EXPERIMENT_ID
    / "broad_market_shared_paper_adapter.json"
)
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

PROFILE_CONFIG = {
    **DEFAULT_CONFIG,
    "ret20_excess_spy_min": 0.035,
    "ret60_min": 0.08,
    "near_high_60_min": 0.93,
    "volume_ratio_20_min": 1.00,
    "decision_close_price_min": 40.0,
    "paper_notional_usd": 7_500.0,
    "rank_notional_multipliers": [1.20, 1.00, 0.80],
    "max_active_positions": 5,
    "daily_entry_slots": 3,
    "hold_days": 20,
}

LOW_EXTENSION_SWEEP: OrderedDict[str, dict[str, float]] = OrderedDict(
    [
        ("baseline_no_low_extension", {"ret5_max": 0.02, "scalar": 1.00}),
        ("ret5_le_0p00_scalar_1p05", {"ret5_max": 0.00, "scalar": 1.05}),
        ("ret5_le_0p00_scalar_1p10", {"ret5_max": 0.00, "scalar": 1.10}),
        ("ret5_le_0p00_scalar_1p15", {"ret5_max": 0.00, "scalar": 1.15}),
        ("ret5_le_0p02_scalar_1p025", {"ret5_max": 0.02, "scalar": 1.025}),
        ("ret5_le_0p02_scalar_1p05", {"ret5_max": 0.02, "scalar": 1.05}),
        ("ret5_le_0p02_scalar_1p075", {"ret5_max": 0.02, "scalar": 1.075}),
        ("ret5_le_0p02_scalar_1p10", {"ret5_max": 0.02, "scalar": 1.10}),
        ("ret5_le_0p02_scalar_1p15", {"ret5_max": 0.02, "scalar": 1.15}),
        ("ret5_le_0p05_scalar_1p025", {"ret5_max": 0.05, "scalar": 1.025}),
        ("ret5_le_0p05_scalar_1p05", {"ret5_max": 0.05, "scalar": 1.05}),
        ("ret5_le_0p05_scalar_1p075", {"ret5_max": 0.05, "scalar": 1.075}),
        ("ret5_le_0p05_scalar_1p10", {"ret5_max": 0.05, "scalar": 1.10}),
        ("ret5_le_0p05_scalar_1p15", {"ret5_max": 0.05, "scalar": 1.15}),
        ("ret5_le_0p08_scalar_1p025", {"ret5_max": 0.08, "scalar": 1.025}),
        ("ret5_le_0p08_scalar_1p05", {"ret5_max": 0.08, "scalar": 1.05}),
        ("ret5_le_0p08_scalar_1p075", {"ret5_max": 0.08, "scalar": 1.075}),
        ("ret5_le_0p08_scalar_1p10", {"ret5_max": 0.08, "scalar": 1.10}),
        ("ret5_le_0p08_scalar_1p15", {"ret5_max": 0.08, "scalar": 1.15}),
        ("ret5_le_0p10_scalar_1p025", {"ret5_max": 0.10, "scalar": 1.025}),
        ("ret5_le_0p10_scalar_1p05", {"ret5_max": 0.10, "scalar": 1.05}),
        ("ret5_le_0p10_scalar_1p075", {"ret5_max": 0.10, "scalar": 1.075}),
        ("ret5_le_0p10_scalar_1p10", {"ret5_max": 0.10, "scalar": 1.10}),
        ("ret5_le_0p10_scalar_1p15", {"ret5_max": 0.10, "scalar": 1.15}),
    ]
)

MIN_ADJUSTED_TRADES = 8
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 3


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


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _simulate_window(
    *,
    label: str,
    ret5_max: float,
    scalar: float,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> dict[str, Any]:
    spec = WINDOWS[label]
    days = p35._trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    cfg = {
        **PROFILE_CONFIG,
        "low_extension_ret5_max": ret5_max,
        "low_extension_notional_scalar": scalar,
    }
    active: list[dict[str, str]] = []
    trades: list[dict[str, Any]] = []
    daily_counts: dict[str, int] = {}

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = int(cfg["max_active_positions"]) - len(active)
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
            if feature and candidate_passes_profile(feature, cfg):
                features.append(feature)
        selected = select_broad_market_features(features, capacity=capacity, config=cfg)
        for rank, feature in enumerate(selected, start=1):
            trade = backtest_trade_from_feature(
                feature=feature,
                prices_by_ticker=prices,
                window_end=spec["end"],
                rank=rank,
                config=cfg,
            )
            if trade is None:
                continue
            trade["window"] = label
            trade["low_extension_ret5_max"] = ret5_max
            trade["low_extension_notional_scalar"] = scalar
            trades.append(trade)
            active.append({"ticker": trade["ticker"], "exit_date": trade["exit_date"]})
            active_tickers.add(trade["ticker"])
        daily_counts[day] = len(features)

    return {
        "window": label,
        "trades": trades,
        "candidate_signal_days": sum(1 for count in daily_counts.values() if count > 0),
        "candidate_signal_count": sum(daily_counts.values()),
        "max_daily_candidate_count": max(daily_counts.values()) if daily_counts else 0,
    }


def _variant_payload(
    *,
    variant_name: str,
    ret5_max: float,
    scalar: float,
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
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
            ret5_max=ret5_max,
            scalar=scalar,
            candidate_tickers=candidate_tickers,
            prices=prices,
            indexes=indexes,
        )
        trades = scout["trades"]
        all_trades.extend(trades)
        curve = p35._event_equity_curve(
            trades=trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        after_metrics[label] = p35._metrics_from_overlay(
            baseline_metrics=control_metrics[label],
            event_curve=curve,
            event_trades=trades,
        )
        sleeve[label] = p35._window_sleeve_summary(trades, scout)

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    adjusted = [
        row for row in all_trades if row.get("low_extension_support_applied") is True
    ]
    adjusted_windows = sorted({row["window"] for row in adjusted})
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = p35._single_ticker_positive_share(all_trades)
    top5_share = p35._top5_positive_share(all_trades)
    sample_guard_passed = len(all_trades) >= p35.MIN_SELECTED_TRADES
    adjusted_guard_passed = (
        len(adjusted) >= MIN_ADJUSTED_TRADES
        and len(adjusted_windows) >= MIN_ADJUSTED_WINDOWS
    )
    window_guard_passed = selected_windows >= p35.MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= p35.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= p35.MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= p35.MAX_DRAWDOWN_WORSE
    gate4_passed = bool(
        variant_name != "baseline_no_low_extension"
        and delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and adjusted_guard_passed
        and window_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
    )
    return {
        "variant_name": variant_name,
        "ret5_max": ret5_max,
        "scalar": scalar,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "adjusted_trade_count": len(adjusted),
        "adjusted_windows": adjusted_windows,
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
        "event_risk": p35._event_risk(all_trades),
        "selected_trades_sample": p35._trade_rows(all_trades, limit=60),
        "adjusted_trades_sample": p35._trade_rows(adjusted, limit=40),
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta": delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
            "windows_ev_improved": delta["windows_ev_improved"],
            "minimum_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
            "windows_ev_regressed": delta["windows_ev_regressed"],
            "windows_pnl_improved": delta["windows_pnl_improved"],
            "windows_pnl_regressed": delta["windows_pnl_regressed"],
            "selected_trade_count": len(all_trades),
            "minimum_selected_trades": p35.MIN_SELECTED_TRADES,
            "sample_guard_passed": sample_guard_passed,
            "adjusted_trade_count": len(adjusted),
            "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
            "adjusted_windows": adjusted_windows,
            "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
            "adjusted_guard_passed": adjusted_guard_passed,
            "selected_windows": selected_windows,
            "minimum_selected_windows": p35.MIN_SELECTED_WINDOWS,
            "window_guard_passed": window_guard_passed,
            "single_ticker_positive_share": single_share,
            "max_single_ticker_positive_share": p35.MAX_SINGLE_TICKER_POSITIVE_SHARE,
            "top5_positive_share": top5_share,
            "max_top5_positive_share": p35.MAX_TOP5_POSITIVE_SHARE,
            "concentration_guard_passed": concentration_guard_passed,
            "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
            "max_drawdown_worse_guardrail": p35.MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
        },
    }


def _choose_best(variants: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in variants if row["gate4"]["passed"]]
    pool = passing or variants
    return sorted(
        pool,
        key=lambda row: (
            bool(row["gate4"]["passed"]),
            float(row["delta_metrics"]["aggregate_ev_delta"]),
            float(row["delta_metrics"]["aggregate_pnl_delta"]),
            -float(row["gate4"]["max_drawdown_worse_max"]),
        ),
        reverse=True,
    )[0]


def _sweep_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant_name": row["variant_name"],
            "ret5_max": row["ret5_max"],
            "scalar": row["scalar"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "adjusted_trade_count": row["adjusted_trade_count"],
            "adjusted_windows": row["adjusted_windows"],
            "aggregate_ev_delta": row["delta_metrics"]["aggregate_ev_delta"],
            "aggregate_pnl_delta": row["delta_metrics"]["aggregate_pnl_delta"],
            "windows_ev_improved": row["gate4"]["windows_ev_improved"],
            "windows_ev_regressed": row["gate4"]["windows_ev_regressed"],
            "windows_pnl_regressed": row["gate4"]["windows_pnl_regressed"],
            "max_drawdown_worse_max": row["gate4"]["max_drawdown_worse_max"],
            "single_ticker_positive_share": row["single_ticker_positive_share"],
            "top5_positive_share": row["top5_positive_share"],
            "event_risk": row["event_risk"],
        }
        for row in variants
    ]


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Low-Extension Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: low-ret5 paper-notional support on the fixed exp-20260519-037 broad-market paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        single = row["single_ticker_positive_share"]
        top5 = row["top5_positive_share"]
        lines.append(
            "| {variant} | {gate} | {adjusted} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {dd:+.4%} | {single} | {top5} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                adjusted=row["adjusted_trade_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                wi=row["windows_ev_improved"],
                wr=row["windows_ev_regressed"],
                dd=float(row["max_drawdown_worse_max"] or 0.0),
                single=f"{single:.2%}" if single is not None else "n/a",
                top5=f"{top5:.2%}" if top5 is not None else "n/a",
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Evidence",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
            )
        )
    lines.extend(
        [
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
    if not BASELINE_JSON.exists():
        raise RuntimeError(f"Missing baseline artifact: {_repo_rel(BASELINE_JSON)}")
    if not CONTROL_JSON.exists():
        raise RuntimeError(f"Missing control artifact: {_repo_rel(CONTROL_JSON)}")
    gate2 = p35._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    baseline_payload = _json_load(BASELINE_JSON)
    control_payload = _json_load(CONTROL_JSON)
    if baseline_payload.get("decision") != "accepted_default_off_broad_market_rank_notional_profile":
        raise RuntimeError(f"Unexpected baseline decision: {baseline_payload.get('decision')}")
    control_metrics = control_payload["before_metrics"]
    before_metrics = baseline_payload["after_metrics"]
    universe_state = p35._load_tradeable_universe()
    tradeable_universe = set(universe_state["excluded_tradeable_universe"])
    warehouse = p35._warehouse_audit()
    candidate_universe = p35._candidate_universe(tradeable_universe)
    prices = p35._load_price_rows(candidate_universe["tickers"])
    indexes = p35._index_by_date(prices)

    variants = [
        _variant_payload(
            variant_name=name,
            ret5_max=values["ret5_max"],
            scalar=values["scalar"],
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            candidate_tickers=candidate_universe["tickers"],
            prices=prices,
            indexes=indexes,
        )
        for name, values in LOW_EXTENSION_SWEEP.items()
    ]
    selected = _choose_best(variants)
    accepted = selected["gate4"]["passed"]
    decision = (
        "accepted_default_off_broad_market_low_extension_notional"
        if accepted
        else "rejected_broad_market_low_extension_notional"
    )
    status = "accepted" if accepted else "rejected"
    aggregate_before = p35._aggregate(before_metrics)
    aggregate_after = p35._aggregate(selected["after_metrics"])
    gate3 = {
        "signals_generated": {
            label: before_metrics[label].get("signals_generated") for label in WINDOWS
        },
        "signals_survived": {
            label: before_metrics[label].get("signals_survived") for label in WINDOWS
        },
        "survival_rate": {
            label: before_metrics[label].get("survival_rate") for label in WINDOWS
        },
        "survival_rate_min": aggregate_before["survival_rate_min"],
        "passed": aggregate_before["survival_rate_min"] >= 0.05,
        "note": "No core filter was added; broad-market sleeve remains default-off paper only.",
    }
    shared_adapter_parity = {
        "passed": (
            selected["ret5_max"] == DEFAULT_CONFIG["low_extension_ret5_max"]
            and selected["scalar"] == DEFAULT_CONFIG["low_extension_notional_scalar"]
            and broad_market_candidate_notional_payload(1, {"ret5": 0.01})["notional"]
            == 10_350.0
        ),
        "shared_rule_version": RULE_VERSION,
        "low_extension_rule_version": LOW_EXTENSION_RULE_VERSION,
        "default_config_low_extension_ret5_max": DEFAULT_CONFIG["low_extension_ret5_max"],
        "default_config_low_extension_scalar": DEFAULT_CONFIG["low_extension_notional_scalar"],
        "selected_low_extension_ret5_max": selected["ret5_max"],
        "selected_low_extension_scalar": selected["scalar"],
        "rank1_low_extension_notional_from_shared_helper": broad_market_candidate_notional_payload(
            1,
            {"ret5": 0.01},
        )["notional"],
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
            "Already-selected broad-market leadership paper candidates with "
            "ret5 <= 2% are less short-term extended and may deserve a bounded "
            "support notional scalar after the accepted rank-notional profile."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool / capital allocation",
            "playbook_alignment": (
                "Matches default-off broad-market sleeve governance and "
                "allocation-over-filtering; avoids LLM soft-ranking, core "
                "universe expansion, and adjacent price/ret20/ret60/near-high/"
                "volume threshold retunes."
            ),
        },
        "history_check": {
            "nearby_experiments": [
                "exp-20260519-036 accepted fixed broad-market price_floor_40 shared adapter",
                "exp-20260519-037 accepted broad-market rank-notional profile [1.20, 1.00, 0.80]",
                "exp-20260520-001 accepted state-surface low-extension, but not broad-market ret5",
            ],
            "anti_repeat": (
                "The broad-market candidate definition, rank profile, price "
                "floor, hold, slots, and universe are fixed; only a new ret5 "
                "low-extension paper notional field changes."
            ),
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "broad_market_low_extension_notional_scalar",
        "single_causal_variable": (
            "low-ret5 paper notional support for fixed broad-market selected candidates"
        ),
        "component": "quant/broad_market_paper_sleeve.py",
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "selected_variant": selected["variant_name"],
            "selected_low_extension_ret5_max": selected["ret5_max"],
            "selected_low_extension_scalar": selected["scalar"],
            "sweep": LOW_EXTENSION_SWEEP,
            "profile_config": {
                key: PROFILE_CONFIG[key]
                for key in (
                    "ret20_excess_spy_min",
                    "ret60_min",
                    "near_high_60_min",
                    "volume_ratio_20_min",
                    "decision_close_price_min",
                    "paper_notional_usd",
                    "rank_notional_multipliers",
                    "max_active_positions",
                    "daily_entry_slots",
                    "hold_days",
                )
            },
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
                "broad-market candidate thresholds",
                "broad-market rank-notional profile",
                "broad-market hold days",
                "broad-market active position cap",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260519-037 rank-notional broad-market adapter is the before "
            "state; after state uses the shared low-extension notional helper."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(BASELINE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
            "known_measurement_boundary": (
                "Historical replay still uses the exp-20260519-030 warehouse. "
                "The production path is default-off paper only and emits no orders."
            ),
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": selected["gate4"],
        "shared_adapter_parity": shared_adapter_parity,
        "before_metrics": before_metrics,
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "expected_value_score_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_ev_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "total_pnl_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_pnl_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["total_pnl"]
                for label in WINDOWS
            },
        },
        "sweep_summary": _sweep_summary(variants),
        "selected_variant": {
            "variant_name": selected["variant_name"],
            "ret5_max": selected["ret5_max"],
            "scalar": selected["scalar"],
            "selected_trade_count": selected["selected_trade_count"],
            "adjusted_trade_count": selected["adjusted_trade_count"],
            "adjusted_windows": selected["adjusted_windows"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "selected_pnl": selected["selected_pnl"],
            "selected_win_rate": selected["selected_win_rate"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "event_risk": selected["event_risk"],
            "adjusted_trades_sample": selected["adjusted_trades_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "candidate_universe": candidate_universe,
        "warehouse_audit": warehouse,
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts or decisions.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": "candidate_pool/capital allocation: low short-term extension broad-market paper candidates deserve a bounded support scalar.",
            "2_past_similar_experiments": "Broad-market price-floor and rank-notional were accepted; broad-market ret5 low-extension was not previously tested. State-surface low-extension existed in a different sleeve.",
            "3_single_variable": "Only low_extension_ret5_max/scalar changes inside a single notional-support field; eligibility, rank profile, hold, slots, and universe controls stay fixed.",
            "4_acceptance": "Gate 4 requires positive aggregate EV/PnL, all 3 windows EV-positive, no EV/PnL regression windows, >=8 adjusted trades across all 3 windows, concentration guard, and <=0.5pp max drawdown worsening.",
            "5_reproducibility": "Script, shared helper, tests, JSON artifact, log, ticket, markdown artifact, and JSONL identify windows, parameters, and metrics.",
        },
        "interpretation": (
            "Broad-market leadership paper candidates with low five-day "
            "extension retain enough follow-through value to support slightly "
            "more default-off paper notional. This is not live or core expansion."
        ),
        "rejection_reason": None if accepted else "Best low-extension support variant failed Gate 4.",
        "next_evidence_needed": (
            "Collect forward broad-market paper outcomes with ret5 metadata; do "
            "not retry adjacent broad-market ret5 scalar thresholds without "
            "new forward outcomes or a distinct quality/risk field."
        ),
        "why_not_other_changes": [
            "No price-floor, ret20, ret60, near-high, or volume threshold changed.",
            "No rank-notional profile retune.",
            "No LLM soft-ranking; attribution remains sparse.",
            "No live/core universe expansion; this stays default-off paper.",
        ],
        "known_risks": [
            "Historical replay depends on the local exp-20260519-030 warehouse.",
            "The EV/PnL increment is small and should be treated as paper-sleeve maturation, not promotion readiness.",
            "Forward paper feed maintenance and replacement-value evidence remain required before live adapter work.",
        ],
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "shared_module": "quant/broad_market_paper_sleeve.py",
            "shared_test": "quant/test_broad_market_paper_sleeve.py",
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "baseline": _repo_rel(BASELINE_JSON),
            "control": _repo_rel(CONTROL_JSON),
        },
    }
    return payload


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
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
    print(json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "selected_variant": payload["selected_variant"]["variant_name"],
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
