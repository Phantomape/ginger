"""exp-20260522-003: broad-market red-day pullback notional.

Alpha search follow-up to exp-20260520-004. The accepted broad-market
price-floor leadership pool, rank-notional profile, low-extension support,
high-volatility support, and trend-persistence support are fixed.

This run changes one causal variable: the default-off paper notional scalar for
already-selected broad-market candidates whose decision-day close is below the
prior close. Core trading, broad-market selection/ranking, exits, universe,
LLM/news, and live/default orders remain unchanged.

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


EXPERIMENT_ID = "exp-20260522-003"
EXPERIMENT_SLUG = "broad_market_red_day_pullback_notional"
BASELINE_EXPERIMENT_ID = "exp-20260520-004"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
import exp_20260520_004_broad_market_trend_persistence_notional as accepted  # noqa: E402


WINDOWS = accepted.WINDOWS
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / BASELINE_EXPERIMENT_ID
    / "broad_market_trend_persistence_notional.json"
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

BASELINE_VARIANT = "baseline_no_red_day_pullback_scalar"
RED_DAY_VARIANTS: OrderedDict[str, dict[str, float]] = OrderedDict(
    [(BASELINE_VARIANT, {"scalar": 1.0})]
)
for scalar in (0.50, 0.75, 0.90, 1.05, 1.10):
    scalar_text = f"{scalar:.2f}".replace(".", "p")
    RED_DAY_VARIANTS[f"red_day_scalar_{scalar_text}"] = {"scalar": scalar}

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


def _decision_day_return_1d(
    *,
    ticker: str,
    decision_date: str,
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> float | None:
    idx = (indexes.get(str(ticker).upper()) or {}).get(str(decision_date)[:10])
    if idx is None or idx <= 0:
        return None
    rows = prices.get(str(ticker).upper()) or []
    if idx >= len(rows):
        return None
    try:
        close = float(rows[idx]["close"])
        prev_close = float(rows[idx - 1]["close"])
    except (KeyError, TypeError, ValueError):
        return None
    if close <= 0 or prev_close <= 0:
        return None
    return round(close / prev_close - 1.0, 6)


def _accepted_window_trades(
    *,
    label: str,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    scout = accepted._simulate_window(
        label=label,
        positive_day_ratio_20_min=accepted.DEFAULT_CONFIG[
            "trend_persistence_positive_day_ratio_20_min"
        ],
        scalar=accepted.DEFAULT_CONFIG["trend_persistence_notional_scalar"],
        candidate_tickers=candidate_tickers,
        prices=prices,
        indexes=indexes,
    )
    enriched: list[dict[str, Any]] = []
    for trade in scout["trades"]:
        row = dict(trade)
        ret1 = _decision_day_return_1d(
            ticker=row["ticker"],
            decision_date=row["decision_date"],
            prices=prices,
            indexes=indexes,
        )
        row["window"] = label
        row["decision_day_return_1d"] = ret1
        row["red_day_pullback_qualified"] = bool(ret1 is not None and ret1 < 0.0)
        enriched.append(row)
    return enriched


def _variant_trades(
    *,
    base_trades: list[dict[str, Any]],
    scalar: float,
) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for trade in base_trades:
        row = dict(trade)
        qualifies = bool(row.get("red_day_pullback_qualified"))
        applies = bool(qualifies and float(scalar) != 1.0)
        if applies:
            row["notional"] = round(float(row["notional"]) * float(scalar), 2)
            row["shares"] = round(float(row["shares"]) * float(scalar), 8)
            row["pnl"] = round(float(row["pnl"]) * float(scalar), 2)
        row["red_day_pullback_scalar"] = scalar if applies else 1.0
        row["red_day_pullback_applied"] = applies
        return_pct = row.get("decision_day_return_1d")
        row["decision_day_return_bucket"] = (
            "red_day" if return_pct is not None and float(return_pct) < 0.0 else "non_red_day"
        )
        trades.append(row)
    return trades


def _trade_rows(trades: list[dict[str, Any]], *, limit: int = 60) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in sorted(trades, key=lambda row: (row["entry_date"], row["ticker"]))[:limit]:
        rows.append(
            {
                "ticker": trade["ticker"],
                "window": trade["window"],
                "decision_date": trade["decision_date"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "pnl": trade["pnl"],
                "net_return_pct": trade["net_return_pct"],
                "rank": trade["rank"],
                "score": trade["score"],
                "decision_day_return_1d": trade.get("decision_day_return_1d"),
                "decision_day_return_bucket": trade.get("decision_day_return_bucket"),
                "red_day_pullback_qualified": trade.get("red_day_pullback_qualified"),
                "red_day_pullback_applied": trade.get("red_day_pullback_applied"),
                "red_day_pullback_scalar": trade.get("red_day_pullback_scalar"),
                "ret20_excess_spy": trade["ret20_excess_spy"],
                "ret5": trade.get("ret5"),
                "ret60": trade["ret60"],
                "volume_ratio_20": trade["volume_ratio_20"],
                "near_high_60": trade["near_high_60"],
                "realized_volatility_20": trade.get("realized_volatility_20"),
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "notional": trade.get("notional"),
            }
        )
    return rows


def _window_sleeve_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    base = p35._window_sleeve_summary(
        trades,
        {
            "trades": trades,
            "candidate_signal_days": None,
            "candidate_signal_count": None,
            "max_daily_candidate_count": None,
        },
    )
    adjusted = [row for row in trades if row.get("red_day_pullback_applied")]
    target = [row for row in trades if row.get("red_day_pullback_qualified")]
    base["red_day_pullback_adjusted_trade_count"] = len(adjusted)
    base["red_day_pullback_target_trade_count"] = len(target)
    base["red_day_pullback_target_pnl"] = round(
        sum(float(row.get("pnl") or 0.0) for row in target),
        2,
    )
    base["sample_trades"] = _trade_rows(trades, limit=25)
    return base


def _variant_payload(
    *,
    variant_name: str,
    scalar: float,
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    base_trades_by_window: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label, spec in WINDOWS.items():
        trades = _variant_trades(
            base_trades=base_trades_by_window[label],
            scalar=scalar,
        )
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
        sleeve[label] = _window_sleeve_summary(trades)

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    adjusted = [row for row in all_trades if row.get("red_day_pullback_applied")]
    target = [row for row in all_trades if row.get("red_day_pullback_qualified")]
    adjusted_windows = sorted({row["window"] for row in adjusted})
    target_windows = sorted({row["window"] for row in target})
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
        variant_name != BASELINE_VARIANT
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
        "scalar": scalar,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "adjusted_trade_count": len(adjusted),
        "adjusted_windows": adjusted_windows,
        "target_trade_count": len(target),
        "target_ticker_count": len({row["ticker"] for row in target}),
        "target_windows": target_windows,
        "target_pnl": round(sum(float(row.get("pnl") or 0.0) for row in target), 2),
        "adjusted_pnl": round(sum(float(row.get("pnl") or 0.0) for row in adjusted), 2),
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": p35._event_risk(all_trades),
        "selected_trades_sample": _trade_rows(all_trades, limit=60),
        "adjusted_trades_sample": _trade_rows(adjusted, limit=40),
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
            "target_trade_count": len(target),
            "target_ticker_count": len({row["ticker"] for row in target}),
            "target_windows": target_windows,
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


def _choose_selected(variants: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in variants if row["gate4"]["passed"]]
    pool = passing or [row for row in variants if row["variant_name"] != BASELINE_VARIANT]
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
            "scalar": row["scalar"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "target_trade_count": row["target_trade_count"],
            "target_ticker_count": row["target_ticker_count"],
            "target_windows": row["target_windows"],
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
        f"# {EXPERIMENT_ID} Broad-Market Red-Day Pullback Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: default-off paper notional scalar for already-selected broad-market candidates with decision-day 1-day return below zero.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Target | dEV | dPnL | EV Improved | EV Regressed | Max DD Worse | Single Share | Top5 Share |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        single = row["single_ticker_positive_share"]
        top5 = row["top5_positive_share"]
        lines.append(
            "| {variant} | {gate} | {target} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {dd:+.4%} | {single} | {top5} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                target=row["target_trade_count"],
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
    expected_decision = "accepted_default_off_broad_market_trend_persistence_notional"
    if baseline_payload.get("decision") != expected_decision:
        raise RuntimeError(f"Unexpected baseline decision: {baseline_payload.get('decision')}")

    control_metrics = control_payload["before_metrics"]
    before_metrics = baseline_payload["after_metrics"]
    universe_state = p35._load_tradeable_universe()
    tradeable_universe = set(universe_state["excluded_tradeable_universe"])
    warehouse = p35._warehouse_audit()
    candidate_universe = p35._candidate_universe(tradeable_universe)
    prices = p35._load_price_rows(candidate_universe["tickers"])
    indexes = p35._index_by_date(prices)
    base_trades_by_window = {
        label: _accepted_window_trades(
            label=label,
            candidate_tickers=candidate_universe["tickers"],
            prices=prices,
            indexes=indexes,
        )
        for label in WINDOWS
    }

    variants = [
        _variant_payload(
            variant_name=name,
            scalar=values["scalar"],
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            base_trades_by_window=base_trades_by_window,
            prices=prices,
        )
        for name, values in RED_DAY_VARIANTS.items()
    ]

    identity = variants[0]
    identity_control = {
        "passed": (
            abs(float(identity["delta_metrics"]["aggregate_ev_delta"])) < 1e-9
            and abs(float(identity["delta_metrics"]["aggregate_pnl_delta"])) < 0.01
            and abs(float(identity["gate4"]["max_drawdown_worse_max"])) < 1e-9
        ),
        "variant_name": identity["variant_name"],
        "aggregate_ev_delta_vs_accepted_artifact": identity["delta_metrics"]["aggregate_ev_delta"],
        "aggregate_pnl_delta_vs_accepted_artifact": identity["delta_metrics"]["aggregate_pnl_delta"],
        "max_drawdown_worse_max_vs_accepted_artifact": identity["gate4"]["max_drawdown_worse_max"],
        "accepted_artifact_candidate_count": (
            (baseline_payload.get("parameters") or {}).get("candidate_count")
        ),
        "current_replay_candidate_count": candidate_universe["candidate_count"],
        "accepted_artifact_excluded_count": (
            (baseline_payload.get("parameters") or {}).get("excluded_count")
        ),
        "current_replay_excluded_count": candidate_universe["excluded_count"],
    }

    selected = _choose_selected(variants)
    selected["gate4"]["identity_control_passed"] = identity_control["passed"]
    if not identity_control["passed"]:
        selected["gate4"]["passed"] = False
    accepted_flag = selected["gate4"]["passed"]
    decision = (
        "accepted_default_off_broad_market_red_day_pullback_notional"
        if accepted_flag
        else (
            "blocked_broad_market_red_day_pullback_identity_drift"
            if not identity_control["passed"]
            else "rejected_broad_market_red_day_pullback_notional"
        )
    )
    status = "accepted" if accepted_flag else ("blocked" if not identity_control["passed"] else "rejected")
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
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "parity_test_added": False,
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
            "Already-selected broad-market leadership candidates that close red on "
            "the decision day may represent weaker pullback follow-through than "
            "green decision-day candidates. A bounded notional scalar can test "
            "whether that context improves replacement value without changing "
            "candidate selection."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses the broad-market leadership maturation lane with a production-visible "
                "context field, while avoiding LLM soft-ranking and event-ret20/volume repeats."
            ),
        },
        "trial_accounting": {
            "trial_family": "broad_market_decision_day_pullback_context",
            "changed_variable": "broad_market_red_day_pullback_notional_scalar",
            "prior_trial_count": 8,
            "nearby_prior_experiments": [
                "exp-20260519-035",
                "exp-20260519-037",
                "exp-20260520-002",
                "exp-20260520-003",
                "exp-20260520-004",
                "exp-20260520-005",
                "exp-20260520-009",
                "exp-20260520-014",
                "exp-20260520-017",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "new_production_visible_decision_day_return_field",
        },
        "change_type": "default_off_paper_allocation",
        "changed_variable": "broad_market_red_day_pullback_notional_scalar",
        "single_causal_variable": (
            "notional scalar for fixed broad-market selected candidates with "
            "decision_day_return_1d < 0"
        ),
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "baseline_variant": BASELINE_VARIANT,
            "selected_variant": selected["variant_name"],
            "selected_red_day_scalar": selected["scalar"],
            "red_day_definition": "decision_day_close / prior_close - 1 < 0",
            "sweep": RED_DAY_VARIANTS,
            "accepted_profile_config": {
                key: accepted.DEFAULT_CONFIG[key]
                for key in (
                    "ret20_excess_spy_min",
                    "ret60_min",
                    "near_high_60_min",
                    "volume_ratio_20_min",
                    "decision_close_price_min",
                    "paper_notional_usd",
                    "rank_notional_multipliers",
                    "low_extension_ret5_max",
                    "low_extension_notional_scalar",
                    "high_volatility_20_min",
                    "high_volatility_notional_scalar",
                    "trend_persistence_positive_day_ratio_20_min",
                    "trend_persistence_notional_scalar",
                    "max_active_positions",
                    "daily_entry_slots",
                    "hold_days",
                )
            },
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_adjusted_windows": MIN_ADJUSTED_WINDOWS,
                "max_drawdown_worse": p35.MAX_DRAWDOWN_WORSE,
                "max_single_ticker_positive_share": p35.MAX_SINGLE_TICKER_POSITIVE_SHARE,
                "max_top5_positive_share": p35.MAX_TOP5_POSITIVE_SHARE,
            },
            "candidate_count": candidate_universe["candidate_count"],
            "excluded_count": candidate_universe["excluded_count"],
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260520-004 trend-persistence broad-market adapter is the before "
            "state; after state changes only the red-day pullback paper notional scalar."
        ),
        "gate1": {
            "passed": identity_control["passed"],
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(BASELINE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
            "identity_control": identity_control,
        },
        "gate2": gate2,
        "gate3": gate3,
        "identity_control": identity_control,
        "gate4": selected["gate4"],
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
            "scalar": selected["scalar"],
            "selected_trade_count": selected["selected_trade_count"],
            "target_trade_count": selected["target_trade_count"],
            "target_ticker_count": selected["target_ticker_count"],
            "target_windows": selected["target_windows"],
            "adjusted_trade_count": selected["adjusted_trade_count"],
            "adjusted_windows": selected["adjusted_windows"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "target_pnl": selected["target_pnl"],
            "adjusted_pnl": selected["adjusted_pnl"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
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
        "production_impact_closeout": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital allocation: broad-market selected red-day pullbacks may "
                "need a notional scalar because the context may separate healthier "
                "continuation from short-term exhaustion."
            ),
            "2_past_similar_experiments": (
                "Broad-market price floor, rank profile, low extension, high volatility, "
                "trend persistence, strong-close crowding, absolute score, recent repeat, "
                "and trend efficiency were tested. Red decision-day return sign was not."
            ),
            "3_single_variable": (
                "Only red_day_pullback scalar changes; broad-market candidate eligibility, "
                "ranking, existing accepted scalars, hold days, slots, and core stack stay fixed."
            ),
            "4_acceptance": (
                "docs/backtesting.md three fixed windows; positive aggregate EV/PnL, "
                "all 3 windows EV-positive, zero EV/PnL regression windows, sample/concentration "
                "guards, and drawdown within 0.5pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260522_003_broad_market_red_day_pullback_notional.py"
            ),
        },
        "history_check": {
            "docs_experiments_directory": "missing",
            "broad_market_identity_drift": {
                "accepted_artifact_candidate_count": identity_control[
                    "accepted_artifact_candidate_count"
                ],
                "current_replay_candidate_count": identity_control[
                    "current_replay_candidate_count"
                ],
                "aggregate_ev_delta_vs_accepted_artifact": identity_control[
                    "aggregate_ev_delta_vs_accepted_artifact"
                ],
                "aggregate_pnl_delta_vs_accepted_artifact": identity_control[
                    "aggregate_pnl_delta_vs_accepted_artifact"
                ],
            },
            "recent_rejections_avoided": [
                "event low-extension/momentum-volume/benchmark-momentum local retunes",
                "state-surface same-family scalar/profile retunes under strict 10% EV gate",
                "LLM soft-ranking without enough replay attribution",
                "SEC semantic fields with zero or sparse same-accession coverage",
            ],
        },
        "interpretation": (
            "This is a broad-market paper alpha search with a production-visible "
            "decision-day context field. If rejected, do not retry nearby red-day "
            "threshold/scalar variants without new forward rows."
        ),
        "rejection_reason": (
            None
            if accepted_flag
            else (
                "Gate 1 identity control failed: the current broad-market warehouse/"
                "candidate universe does not reproduce the accepted exp-20260520-004 "
                "baseline, so red-day scalar deltas are not acceptance evidence."
                if not identity_control["passed"]
                else "Red-day pullback scalar did not clear the broad-market three-window Gate 4."
            )
        ),
        "next_evidence_needed": (
            "Freeze or version the broad-market candidate universe used by accepted "
            "paper replays, then rerun identity control before testing additional "
            "broad-market local allocation fields. Otherwise move to a distinct "
            "alpha lane with stable replay inputs."
        ),
        "why_not_other_changes": (
            "Skipped event ret20/volume/extension because the recent family is over-mined "
            "and drawdown-fragile; skipped state-surface because the strict 10% EV gate "
            "makes another notional tweak low value; skipped LLM/SEC due sparse attribution."
        ),
        "known_risks": [
            "High multiple-testing risk in broad-market local allocation fields.",
            "This is default-off paper evidence only; it does not justify live/default orders.",
        ],
        "related_files": {
            "script": _repo_rel(Path(__file__)),
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
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "trial_accounting": payload["trial_accounting"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "production_impact_closeout": payload["production_impact_closeout"],
        "why_not_other_changes": payload["why_not_other_changes"],
        "known_risks": payload["known_risks"],
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
        "trial_accounting": payload["trial_accounting"],
        "gate4": payload["gate4"],
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
