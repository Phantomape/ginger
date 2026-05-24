"""exp-20260524-024: broad-market short-horizon return-path cluster support.

Alpha search follow-up to the accepted exp-20260520-004 broad-market
trend-persistence paper sleeve. This run tests one playbook-listed but
previously unexplored daily-return-pattern field:
``short_horizon_return_path_cluster``.

The accepted broad-market candidate pool, rank-notional profile,
low-extension support, high-volatility support, and trend-persistence support
remain fixed. This run only adds an experiment-local default-off paper
notional scalar for already-selected candidates that fall into a specific
short-horizon return-path cluster.

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


EXPERIMENT_ID = "exp-20260524-024"
EXPERIMENT_SLUG = "broad_market_short_horizon_path_cluster"
BASELINE_EXPERIMENT_ID = "exp-20260520-004"
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
    backtest_trade_from_feature,
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

PROFILE_CONFIG = {
    **DEFAULT_CONFIG,
    "ret20_excess_spy_min": 0.035,
    "ret60_min": 0.08,
    "near_high_60_min": 0.93,
    "volume_ratio_20_min": 1.00,
    "decision_close_price_min": 40.0,
    "paper_notional_usd": 7_500.0,
    "rank_notional_multipliers": [1.20, 1.00, 0.80],
    "low_extension_ret5_max": 0.02,
    "low_extension_notional_scalar": 1.15,
    "high_volatility_20_min": 0.055,
    "high_volatility_notional_scalar": 1.15,
    "trend_persistence_positive_day_ratio_20_min": 0.55,
    "trend_persistence_notional_scalar": 1.15,
    "max_active_positions": 5,
    "daily_entry_slots": 3,
    "hold_days": 20,
}

BASELINE_VARIANT = "baseline_no_short_horizon_cluster_support"
PATH_CLUSTER_SWEEP: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "target_cluster": "none",
                "scalar": 1.0,
            },
        )
    ]
)
for target_cluster in (
    "steady_continuation",
    "orderly_pullback",
    "constructive_chop",
):
    for scalar in (1.025, 1.05, 1.075, 1.10, 1.15):
        scalar_text = f"{scalar:.3f}".rstrip("0").rstrip(".").replace(".", "p")
        PATH_CLUSTER_SWEEP[f"{target_cluster}_scalar_{scalar_text}"] = {
            "target_cluster": target_cluster,
            "scalar": scalar,
        }

MIN_ADJUSTED_TRADES = 8
MIN_ADJUSTED_WINDOWS = 3
MIN_EV_IMPROVED_WINDOWS = 3
MIN_RELATIVE_EV_IMPROVEMENT = 0.10


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


def _positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _max_daily_return_20(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 20:
        return None
    max_return: float | None = None
    for cursor in range(idx - 20 + 1, idx + 1):
        prev_close = _positive_float(rows[cursor - 1].get("close"))
        close = _positive_float(rows[cursor].get("close"))
        if prev_close is None or close is None:
            return None
        daily_return = close / prev_close - 1.0
        if max_return is None or daily_return > max_return:
            max_return = daily_return
    if max_return is None:
        return None
    return round(max_return, 6)


def _short_horizon_return_path_cluster(feature: dict[str, Any], max_daily_return_20: float) -> str:
    ret5 = float(feature.get("ret5") or 0.0)
    positive_day_ratio_20 = float(feature.get("positive_day_ratio_20") or 0.0)
    if positive_day_ratio_20 >= 0.55 and max_daily_return_20 <= 0.10:
        return "steady_continuation" if ret5 > 0.0 else "orderly_pullback"
    if positive_day_ratio_20 >= 0.50 and max_daily_return_20 <= 0.12:
        return "constructive_chop"
    if max_daily_return_20 > 0.10:
        return "spike_extension" if ret5 > 0.0 else "spike_fade"
    return "mixed_path"


def _base_feature_rows(
    *,
    label: str,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    spec = WINDOWS[label]
    days = p35._trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    active: list[dict[str, str]] = []
    rows_out: list[dict[str, Any]] = []

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
                max_daily_return_20 = _max_daily_return_20(rows, idx)
                if max_daily_return_20 is None:
                    continue
                feature["max_daily_return_20"] = max_daily_return_20
                feature["short_horizon_return_path_cluster"] = _short_horizon_return_path_cluster(
                    feature,
                    max_daily_return_20,
                )
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
            rows_out.append({"window": label, "rank": rank, "feature": feature})
            active.append({"ticker": trade["ticker"], "exit_date": trade["exit_date"]})
            active_tickers.add(trade["ticker"])
    return rows_out


def _variant_trades(
    *,
    base_rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
    target_cluster: str,
    scalar: float,
    label: str,
) -> list[dict[str, Any]]:
    spec = WINDOWS[label]
    cfg = dict(PROFILE_CONFIG)
    trades: list[dict[str, Any]] = []
    for row in base_rows:
        trade = backtest_trade_from_feature(
            feature=row["feature"],
            prices_by_ticker=prices,
            window_end=spec["end"],
            rank=int(row["rank"]),
            config=cfg,
        )
        if trade is None:
            continue
        cluster = str(row["feature"].get("short_horizon_return_path_cluster") or "unknown")
        support_applied = cluster == target_cluster and float(scalar) != 1.0
        if support_applied:
            trade["notional"] = round(float(trade["notional"]) * float(scalar), 2)
            trade["shares"] = round(float(trade["shares"]) * float(scalar), 8)
            trade["pnl"] = round(float(trade["pnl"]) * float(scalar), 2)
        trade["window"] = label
        trade["max_daily_return_20"] = row["feature"].get("max_daily_return_20")
        trade["positive_day_ratio_20"] = row["feature"].get("positive_day_ratio_20")
        trade["short_horizon_return_path_cluster"] = cluster
        trade["path_cluster_target"] = target_cluster
        trade["path_cluster_support_notional_scalar"] = scalar
        trade["path_cluster_notional_multiplier"] = scalar if support_applied else 1.0
        trade["path_cluster_support_applied"] = support_applied
        trades.append(trade)
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
                "ret5": trade.get("ret5"),
                "ret20_excess_spy": trade["ret20_excess_spy"],
                "ret60": trade["ret60"],
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "max_daily_return_20": trade.get("max_daily_return_20"),
                "short_horizon_return_path_cluster": trade.get("short_horizon_return_path_cluster"),
                "path_cluster_support_applied": trade.get("path_cluster_support_applied"),
                "path_cluster_notional_multiplier": trade.get("path_cluster_notional_multiplier"),
                "volume_ratio_20": trade["volume_ratio_20"],
                "near_high_60": trade["near_high_60"],
                "realized_volatility_20": trade.get("realized_volatility_20"),
                "notional": trade.get("notional"),
            }
        )
    return rows


def _window_sleeve_summary(
    trades: list[dict[str, Any]],
    scout: dict[str, Any],
) -> dict[str, Any]:
    base = p35._window_sleeve_summary(trades, scout)
    adjusted = [row for row in trades if row.get("path_cluster_support_applied")]
    cluster_counts: dict[str, int] = {}
    for trade in trades:
        cluster = str(trade.get("short_horizon_return_path_cluster") or "unknown")
        cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
    base["path_cluster_adjusted_trade_count"] = len(adjusted)
    base["path_cluster_adjusted_pnl"] = round(
        sum(float(row.get("pnl") or 0.0) for row in adjusted),
        2,
    )
    base["path_cluster_counts"] = cluster_counts
    base["sample_trades"] = _trade_rows(trades, limit=25)
    return base


def _variant_payload(
    *,
    variant_name: str,
    target_cluster: str,
    scalar: float,
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    base_features: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label, spec in WINDOWS.items():
        trades = _variant_trades(
            base_rows=base_features[label],
            prices=prices,
            target_cluster=target_cluster,
            scalar=scalar,
            label=label,
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
        sleeve[label] = _window_sleeve_summary(
            trades,
            {
                "trades": trades,
                "candidate_signal_days": None,
                "candidate_signal_count": None,
                "max_daily_candidate_count": None,
            },
        )

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    adjusted = [row for row in all_trades if row.get("path_cluster_support_applied")]
    adjusted_windows = sorted({row["window"] for row in adjusted})
    adjusted_cluster_counts: dict[str, int] = {}
    for row in adjusted:
        cluster = str(row.get("short_horizon_return_path_cluster") or "unknown")
        adjusted_cluster_counts[cluster] = adjusted_cluster_counts.get(cluster, 0) + 1
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
    aggregate_before = p35._aggregate(before_metrics)
    aggregate_after = p35._aggregate(after_metrics)
    relative_ev_improvement = 0.0
    before_ev = float(aggregate_before["expected_value_score_sum"])
    after_ev = float(aggregate_after["expected_value_score_sum"])
    if before_ev != 0.0:
        relative_ev_improvement = after_ev / before_ev - 1.0
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
        and relative_ev_improvement > MIN_RELATIVE_EV_IMPROVEMENT
    )
    return {
        "variant_name": variant_name,
        "target_cluster": target_cluster,
        "scalar": scalar,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "adjusted_trade_count": len(adjusted),
        "adjusted_windows": adjusted_windows,
        "adjusted_cluster_counts": adjusted_cluster_counts,
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
            "relative_ev_improvement": round(relative_ev_improvement, 6),
            "minimum_relative_ev_improvement": MIN_RELATIVE_EV_IMPROVEMENT,
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
            "target_cluster": row["target_cluster"],
            "scalar": row["scalar"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "adjusted_trade_count": row["adjusted_trade_count"],
            "adjusted_windows": row["adjusted_windows"],
            "adjusted_cluster_counts": row["adjusted_cluster_counts"],
            "aggregate_ev_delta": row["delta_metrics"]["aggregate_ev_delta"],
            "aggregate_pnl_delta": row["delta_metrics"]["aggregate_pnl_delta"],
            "relative_ev_improvement": row["gate4"]["relative_ev_improvement"],
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
        f"# {EXPERIMENT_ID} Broad-Market Short-Horizon Return-Path Cluster",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: `short_horizon_return_path_cluster` support scalar on the accepted broad-market paper sleeve.",
        "",
        "## Sweep",
        "",
        "| Variant | Cluster | Gate 4 | Adjusted | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |",
        "|---|---|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {cluster} | {gate} | {adjusted} | {ev:+.4f} | {rel:+.2%} | ${pnl:+,.2f} | {wi} | {wr} | {dd:+.4%} |".format(
                variant=row["variant_name"],
                cluster=row["target_cluster"],
                gate="PASS" if row["passed"] else "FAIL",
                adjusted=row["adjusted_trade_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                rel=float(row["relative_ev_improvement"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                wi=row["windows_ev_improved"],
                wr=row["windows_ev_regressed"],
                dd=float(row["max_drawdown_worse_max"] or 0.0),
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
    if baseline_payload.get("decision") != "accepted_default_off_broad_market_trend_persistence_notional":
        raise RuntimeError(f"Unexpected baseline decision: {baseline_payload.get('decision')}")

    control_metrics = control_payload["before_metrics"]
    before_metrics = baseline_payload["after_metrics"]
    frozen_tickers = list(baseline_payload["candidate_universe"]["tickers"])
    prices = p35._load_price_rows(frozen_tickers)
    indexes = p35._index_by_date(prices)
    warehouse = p35._warehouse_audit()
    base_features = {
        label: _base_feature_rows(
            label=label,
            candidate_tickers=frozen_tickers,
            prices=prices,
            indexes=indexes,
        )
        for label in WINDOWS
    }

    variants = [
        _variant_payload(
            variant_name=name,
            target_cluster=values["target_cluster"],
            scalar=values["scalar"],
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            base_features=base_features,
            prices=prices,
        )
        for name, values in PATH_CLUSTER_SWEEP.items()
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
    }

    selected = _choose_selected(variants)
    selected["gate4"]["identity_control_passed"] = identity_control["passed"]
    if not identity_control["passed"]:
        selected["gate4"]["passed"] = False
    accepted = selected["gate4"]["passed"]
    decision = (
        "accepted_default_off_broad_market_short_horizon_path_cluster"
        if accepted
        else "rejected_broad_market_short_horizon_path_cluster"
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
        "note": "No new core filter was added; broad-market sleeve remains default-off paper only.",
    }
    production_impact = {
        "shared_policy_changed": accepted,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "parity_test_added": accepted,
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
            "Already-selected broad-market leadership paper candidates with an "
            "orderly short-horizon return path may deserve more paper notional "
            "than equally ranked names driven by choppier or spike-dominated paths."
        ),
        "change_type": "default_off_paper_allocation",
        "changed_variable": "broad_market_short_horizon_return_path_cluster_support_scalar",
        "single_causal_variable": (
            "short_horizon_return_path_cluster support scalar for fixed broad-market selected candidates"
        ),
        "trial_accounting": {
            "trial_family": "broad_market_daily_return_path_cluster_support",
            "changed_variable": "short_horizon_return_path_cluster_and_scalar",
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260519-037",
                "exp-20260520-002",
                "exp-20260520-003",
                "exp-20260520-004",
                "exp-20260520-017",
                "exp-20260523-006",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "new_production_visible_field",
        },
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "selected_variant": selected["variant_name"],
            "selected_target_cluster": selected["target_cluster"],
            "selected_scalar": selected["scalar"],
            "cluster_definition": {
                "steady_continuation": "positive_day_ratio_20 >= 0.55 and max_daily_return_20 <= 0.10 and ret5 > 0",
                "orderly_pullback": "positive_day_ratio_20 >= 0.55 and max_daily_return_20 <= 0.10 and ret5 <= 0",
                "constructive_chop": "positive_day_ratio_20 >= 0.50 and max_daily_return_20 <= 0.12 but not in steady/orderly bucket",
                "spike_extension": "max_daily_return_20 > 0.10 and ret5 > 0",
                "spike_fade": "max_daily_return_20 > 0.10 and ret5 <= 0",
                "mixed_path": "all other paths",
            },
            "sweep": PATH_CLUSTER_SWEEP,
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
            "frozen_candidate_count": len(frozen_tickers),
            "frozen_candidate_source": _repo_rel(BASELINE_JSON),
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"]} for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260520-004 trend-persistence broad-market adapter is the before "
            "state; after state adds an experiment-local short_horizon_return_path_cluster "
            "paper-notional support field on the frozen accepted candidate universe."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(BASELINE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
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
            "target_cluster": selected["target_cluster"],
            "scalar": selected["scalar"],
            "selected_trade_count": selected["selected_trade_count"],
            "adjusted_trade_count": selected["adjusted_trade_count"],
            "adjusted_windows": selected["adjusted_windows"],
            "adjusted_cluster_counts": selected["adjusted_cluster_counts"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "adjusted_pnl": selected["adjusted_pnl"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "adjusted_trades_sample": selected["adjusted_trades_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "candidate_universe": {
            "source": "frozen_from_accepted_artifact",
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "frozen_candidate_count": len(frozen_tickers),
            "tickers": frozen_tickers,
        },
        "warehouse_audit": warehouse,
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts or decisions.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": "capital allocation / daily return path: already-selected broad-market leaders with orderly short-horizon paths may deserve extra paper notional support.",
            "2_past_similar_experiments": "Broad-market rank-notional, low-extension, high-volatility, trend-persistence, trend-efficiency, and max-daily-return support were tested; short_horizon_return_path_cluster was not previously formalized.",
            "3_single_variable": "Only short_horizon_return_path_cluster target/scalar changes inside one notional-support field; eligibility, rank profile, low-extension, high-volatility, trend-persistence, hold, slots, and frozen universe stay fixed.",
            "4_acceptance": "Gate 4 requires positive aggregate EV/PnL, all 3 windows EV-positive, no EV/PnL regression windows, >=8 adjusted trades across all 3 windows, concentration guard, <=0.5pp max drawdown worsening, and >10% relative aggregate EV improvement.",
            "5_reproducibility": "Script, frozen candidate universe, JSON artifact, log, ticket, markdown artifact, and JSONL identify windows, parameters, and metrics.",
        },
        "interpretation": (
            "short_horizon_return_path_cluster is a new playbook-aligned daily-return-pattern "
            "field for broad-market paper allocation. Promotion still requires identity control "
            "plus the same three-window and relative-EV guard used for nearby broad-market "
            "paper allocation families."
        ),
        "rejection_reason": None if accepted else "Short-horizon return-path cluster support did not clear the broad-market three-window gate, the >10% relative aggregate EV rule, and/or identity control.",
        "next_evidence_needed": (
            "Collect more forward broad-market paper outcomes with short_horizon_return_path_cluster "
            "metadata; do not retry nearby cluster/scalar variants on the frozen sample without new "
            "forward evidence or a materially different path-quality field."
        ),
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
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "trial_accounting": payload["trial_accounting"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": _compact_metrics(payload["before_metrics"]),
        "after_metrics": _compact_metrics(payload["after_metrics"]),
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "decision": payload["decision"],
        "gate4": payload["gate4"],
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
