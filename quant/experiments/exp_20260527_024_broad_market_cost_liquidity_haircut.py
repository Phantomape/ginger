"""exp-20260527-024: broad-market cost/liquidity haircut.

Alpha search. Uses the accepted exp-20260520-004 broad-market paper sleeve
and tests one causal variable: whether already-selected broad-market paper
trades with high ex-ante transaction-cost/liquidity proxy deserve lower paper
notional.

The proxy only uses free OHLCV data known at the signal decision date:
20-session median dollar volume and the source trade's 20-day realized
volatility. This does not change core signal generation, ranking, exits,
LLM/news decisions, live orders, or production default-off paper behavior.
Positive replay evidence would still require a shared default-off adapter
before promotion.

No JavaScript is used.
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


EXPERIMENT_ID = "exp-20260527-024"
EXPERIMENT_SLUG = "broad_market_cost_liquidity_haircut"
SOURCE_EXPERIMENT_ID = "exp-20260520-004"
SOURCE_SLUG = "broad_market_trend_persistence_notional"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"
RULE_VERSION = "broad_market_cost_liquidity_haircut_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
import exp_20260520_004_broad_market_trend_persistence_notional as e004  # noqa: E402
import exp_20260527_901_broad_market_sector_open_crowding_haircut as prior  # noqa: E402


WINDOWS = e004.WINDOWS
SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / f"{SOURCE_SLUG}.json"
)
CONTROL_JSON = e004.CONTROL_JSON
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

COST_BPS_HIGH_THRESHOLD = 35.0
COST_HAIRCUT_SWEEP: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            "baseline_no_cost_liquidity_haircut",
            {"high_cost_scalar": 1.00},
        ),
        (
            "high_expected_cost_scalar_0p90",
            {"high_cost_scalar": 0.90},
        ),
        (
            "high_expected_cost_scalar_0p80",
            {"high_cost_scalar": 0.80},
        ),
        (
            "high_expected_cost_scalar_0p65",
            {"high_cost_scalar": 0.65},
        ),
        (
            "high_expected_cost_scalar_0p50",
            {"high_cost_scalar": 0.50},
        ),
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            key: value
            for key, value in row.items()
            if key != "combined_equity_curve"
        }
        for label, row in metrics.items()
    }


def _lookup_price_index(
    rows: list[dict[str, Any]],
    by_date: dict[str, int],
    day: str,
) -> int | None:
    idx = by_date.get(day)
    if idx is not None:
        return idx
    fallback: int | None = None
    for row_idx, row in enumerate(rows):
        row_day = str(row.get("date") or "")
        if row_day > day:
            break
        fallback = row_idx
    return fallback


def _median_dollar_volume_20(
    *,
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    ticker: str,
    decision_date: str,
) -> float | None:
    rows = prices.get(str(ticker).upper()) or []
    idx = _lookup_price_index(rows, indexes.get(str(ticker).upper()) or {}, decision_date)
    if idx is None:
        return None
    window = rows[max(0, idx - 19) : idx + 1]
    values = [
        float(row.get("close") or 0.0) * float(row.get("volume") or 0.0)
        for row in window
        if float(row.get("close") or 0.0) > 0.0 and float(row.get("volume") or 0.0) > 0.0
    ]
    if not values:
        return None
    return float(median(values))


def _expected_round_trip_cost_bps(trade: dict[str, Any], median_dollar_volume_20: float | None) -> float:
    vol = float(trade.get("realized_volatility_20") or 0.0)
    if median_dollar_volume_20 is None or median_dollar_volume_20 <= 0:
        liquidity_bps = 24.0
    else:
        liquidity_bps = min(32.0, 80.0 / math.sqrt(max(median_dollar_volume_20 / 1_000_000.0, 1.0)))
    volatility_bps = min(42.0, max(0.0, vol * 10000.0 * 0.08))
    return round(3.0 + liquidity_bps + volatility_bps, 4)


def _cost_bucket(cost_bps: float) -> str:
    if cost_bps >= 50.0:
        return "very_high"
    if cost_bps >= COST_BPS_HIGH_THRESHOLD:
        return "high"
    if cost_bps >= 25.0:
        return "medium"
    return "low"


def _scale_trade_notional(
    trade: dict[str, Any],
    *,
    scalar: float,
    applied: bool,
    cost_bps: float,
    cost_bucket: str,
    median_dollar_volume_20: float | None,
) -> dict[str, Any]:
    out = dict(trade)
    original_notional = float(out.get("notional") or 0.0)
    original_shares = float(out.get("shares") or 0.0)
    original_pnl = float(out.get("pnl") or 0.0)
    effective_scalar = scalar if applied else 1.0
    out["pre_cost_liquidity_notional"] = round(original_notional, 2)
    out["pre_cost_liquidity_shares"] = round(original_shares, 8)
    out["pre_cost_liquidity_pnl"] = round(original_pnl, 2)
    out["cost_liquidity_rule_version"] = RULE_VERSION
    out["expected_round_trip_cost_bps"] = cost_bps
    out["expected_round_trip_cost_bucket"] = cost_bucket
    out["median_dollar_volume_20"] = (
        round(float(median_dollar_volume_20), 2)
        if median_dollar_volume_20 is not None
        else None
    )
    out["cost_liquidity_haircut_applied"] = bool(applied)
    out["cost_liquidity_haircut_scalar"] = round(effective_scalar, 6)
    out["notional"] = round(original_notional * effective_scalar, 2)
    out["shares"] = round(original_shares * effective_scalar, 8)
    out["pnl"] = round(original_pnl * effective_scalar, 2)
    return out


def _apply_cost_liquidity_haircut(
    trades: list[dict[str, Any]],
    *,
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    high_cost_scalar: float,
) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for raw in trades:
        median_dv_20 = _median_dollar_volume_20(
            prices=prices,
            indexes=indexes,
            ticker=str(raw.get("ticker") or ""),
            decision_date=str(raw.get("decision_date") or ""),
        )
        cost_bps = _expected_round_trip_cost_bps(raw, median_dv_20)
        bucket = _cost_bucket(cost_bps)
        applied = bool(
            cost_bps >= COST_BPS_HIGH_THRESHOLD
            and float(high_cost_scalar) < 1.0
        )
        adjusted.append(
            _scale_trade_notional(
                raw,
                scalar=float(high_cost_scalar),
                applied=applied,
                cost_bps=cost_bps,
                cost_bucket=bucket,
                median_dollar_volume_20=median_dv_20,
            )
        )
    return adjusted


def _trade_rows(trades: list[dict[str, Any]], *, limit: int = 40) -> list[dict[str, Any]]:
    rows = []
    for trade in sorted(trades, key=lambda row: (row["entry_date"], row["ticker"]))[:limit]:
        rows.append(
            {
                "ticker": trade["ticker"],
                "window": trade.get("window"),
                "decision_date": trade["decision_date"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "rank": trade.get("rank"),
                "score": trade.get("score"),
                "notional": trade.get("notional"),
                "pre_cost_liquidity_notional": trade.get("pre_cost_liquidity_notional"),
                "pnl": trade.get("pnl"),
                "pre_cost_liquidity_pnl": trade.get("pre_cost_liquidity_pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "expected_round_trip_cost_bps": trade.get("expected_round_trip_cost_bps"),
                "expected_round_trip_cost_bucket": trade.get("expected_round_trip_cost_bucket"),
                "median_dollar_volume_20": trade.get("median_dollar_volume_20"),
                "cost_liquidity_haircut_applied": trade.get("cost_liquidity_haircut_applied"),
                "cost_liquidity_haircut_scalar": trade.get("cost_liquidity_haircut_scalar"),
                "ret20_excess_spy": trade.get("ret20_excess_spy"),
                "ret60": trade.get("ret60"),
                "ret5": trade.get("ret5"),
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "realized_volatility_20": trade.get("realized_volatility_20"),
            }
        )
    return rows


def _cost_bucket_counts(trades: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trade in trades:
        counts[str(trade.get("expected_round_trip_cost_bucket") or "unknown")] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _cost_bucket_pnl(trades: list[dict[str, Any]]) -> dict[str, float]:
    pnl: dict[str, float] = {}
    for trade in trades:
        bucket = str(trade.get("expected_round_trip_cost_bucket") or "unknown")
        pnl[bucket] = pnl.get(bucket, 0.0) + float(trade.get("pnl") or 0.0)
    return {
        bucket: round(value, 2)
        for bucket, value in sorted(pnl.items(), key=lambda item: (-item[1], item[0]))
    }


def _window_sleeve_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    adjusted = [row for row in trades if row.get("cost_liquidity_haircut_applied")]
    pre_adjusted_pnl = sum(float(row.get("pre_cost_liquidity_pnl") or 0.0) for row in adjusted)
    adjusted_pnl = sum(float(row.get("pnl") or 0.0) for row in adjusted)
    pre_notional = sum(float(row.get("pre_cost_liquidity_notional") or 0.0) for row in adjusted)
    post_notional = sum(float(row.get("notional") or 0.0) for row in adjusted)
    wins = sum(1 for row in trades if float(row.get("pnl") or 0.0) > 0)
    cost_values = [
        float(row["expected_round_trip_cost_bps"])
        for row in trades
        if row.get("expected_round_trip_cost_bps") is not None
    ]
    return {
        "trade_count": len(trades),
        "pnl": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "cost_liquidity_adjusted_trade_count": len(adjusted),
        "cost_liquidity_pre_adjusted_pnl": round(pre_adjusted_pnl, 2),
        "cost_liquidity_adjusted_pnl": round(adjusted_pnl, 2),
        "cost_liquidity_pnl_removed": round(pre_adjusted_pnl - adjusted_pnl, 2),
        "cost_liquidity_notional_removed": round(pre_notional - post_notional, 2),
        "expected_cost_bps_median": round(median(cost_values), 4) if cost_values else None,
        "expected_cost_bps_max": round(max(cost_values), 4) if cost_values else None,
        "cost_bucket_counts": _cost_bucket_counts(trades),
        "cost_bucket_pnl": _cost_bucket_pnl(trades),
        "adjusted_cost_bucket_counts": _cost_bucket_counts(adjusted),
        "sample_trades": _trade_rows(trades, limit=25),
        "adjusted_trades_sample": _trade_rows(adjusted, limit=25),
    }


def _variant_payload(
    *,
    variant_name: str,
    high_cost_scalar: float,
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    baseline_trades_by_window: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    baseline_replay_parity_passed: bool,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label, spec in WINDOWS.items():
        adjusted_trades = _apply_cost_liquidity_haircut(
            baseline_trades_by_window[label],
            prices=prices,
            indexes=indexes,
            high_cost_scalar=high_cost_scalar,
        )
        for trade in adjusted_trades:
            trade["window"] = label
        all_trades.extend(adjusted_trades)
        curve = p35._event_equity_curve(
            trades=adjusted_trades,
            prices=prices,
            start=spec["start"],
            end=spec["end"],
        )
        after_metrics[label] = p35._metrics_from_overlay(
            baseline_metrics=control_metrics[label],
            event_curve=curve,
            event_trades=adjusted_trades,
        )
        sleeve[label] = _window_sleeve_summary(adjusted_trades)

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    adjusted = [row for row in all_trades if row.get("cost_liquidity_haircut_applied")]
    adjusted_windows = sorted({row["window"] for row in adjusted})
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = p35._single_ticker_positive_share(all_trades)
    top5_share = p35._top5_positive_share(all_trades)
    sample_guard_passed = len(all_trades) >= p35.MIN_SELECTED_TRADES
    adjusted_guard_passed = len(adjusted) >= MIN_ADJUSTED_TRADES and len(adjusted_windows) >= MIN_ADJUSTED_WINDOWS
    window_guard_passed = selected_windows >= p35.MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= p35.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= p35.MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= p35.MAX_DRAWDOWN_WORSE
    gate4_passed = bool(
        variant_name != "baseline_no_cost_liquidity_haircut"
        and baseline_replay_parity_passed
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
        "high_cost_scalar": high_cost_scalar,
        "cost_bps_high_threshold": COST_BPS_HIGH_THRESHOLD,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "adjusted_trade_count": len(adjusted),
        "adjusted_windows": adjusted_windows,
        "adjusted_pnl": round(sum(float(row.get("pnl") or 0.0) for row in adjusted), 2),
        "pre_adjusted_pnl": round(
            sum(float(row.get("pre_cost_liquidity_pnl") or 0.0) for row in adjusted),
            2,
        ),
        "notional_removed": round(
            sum(
                float(row.get("pre_cost_liquidity_notional") or 0.0)
                - float(row.get("notional") or 0.0)
                for row in adjusted
            ),
            2,
        ),
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": p35._event_risk(all_trades),
        "cost_bucket_counts": _cost_bucket_counts(all_trades),
        "cost_bucket_pnl": _cost_bucket_pnl(all_trades),
        "adjusted_cost_bucket_counts": _cost_bucket_counts(adjusted),
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
            "baseline_replay_parity_passed": baseline_replay_parity_passed,
        },
    }


def _choose_selected(variants: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in variants if row["gate4"]["passed"]]
    pool = passing or [
        row
        for row in variants
        if row["variant_name"] != "baseline_no_cost_liquidity_haircut"
    ]
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
            "high_cost_scalar": row["high_cost_scalar"],
            "cost_bps_high_threshold": row["cost_bps_high_threshold"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "adjusted_trade_count": row["adjusted_trade_count"],
            "adjusted_windows": row["adjusted_windows"],
            "pre_adjusted_pnl": row["pre_adjusted_pnl"],
            "adjusted_pnl": row["adjusted_pnl"],
            "notional_removed": row["notional_removed"],
            "aggregate_ev_delta": row["delta_metrics"]["aggregate_ev_delta"],
            "aggregate_pnl_delta": row["delta_metrics"]["aggregate_pnl_delta"],
            "windows_ev_improved": row["gate4"]["windows_ev_improved"],
            "windows_ev_regressed": row["gate4"]["windows_ev_regressed"],
            "windows_pnl_regressed": row["gate4"]["windows_pnl_regressed"],
            "max_drawdown_worse_max": row["gate4"]["max_drawdown_worse_max"],
            "single_ticker_positive_share": row["single_ticker_positive_share"],
            "top5_positive_share": row["top5_positive_share"],
            "cost_bucket_counts": row["cost_bucket_counts"],
            "adjusted_cost_bucket_counts": row["adjusted_cost_bucket_counts"],
            "event_risk": row["event_risk"],
        }
        for row in variants
    ]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Cost/Liquidity Haircut",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: paper-notional haircut for accepted broad-market",
        "paper entries whose decision-date OHLCV cost/liquidity proxy is high.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | PnL Regressed | Max DD Worse |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {gate} | {adjusted} | {ev:+.4f} | ${pnl:+,.2f} | {wi} | {wr} | {pr} | {dd:+.4%} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                adjusted=row["adjusted_trade_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                wi=row["windows_ev_improved"],
                wr=row["windows_ev_regressed"],
                pr=row["windows_pnl_regressed"],
                dd=float(row["max_drawdown_worse_max"] or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Three-Window Evidence",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted Trades |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["broad_market_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {adj} |".format(
                label=label,
                bev=float(before["expected_value_score"]),
                aev=float(after["expected_value_score"]),
                dev=float(delta["expected_value_score"]),
                bpnl=float(before["total_pnl"]),
                apnl=float(after["total_pnl"]),
                dpnl=float(delta["total_pnl"]),
                adj=sleeve["cost_liquidity_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Baseline Replay Parity",
            "",
            "```json",
            json.dumps(payload["baseline_replay_parity"], indent=2, sort_keys=True),
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
    if not SOURCE_JSON.exists():
        raise RuntimeError(f"Missing source artifact: {_repo_rel(SOURCE_JSON)}")
    if not CONTROL_JSON.exists():
        raise RuntimeError(f"Missing control artifact: {_repo_rel(CONTROL_JSON)}")
    gate2 = p35._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_payload = _json_load(SOURCE_JSON)
    control_payload = _json_load(CONTROL_JSON)
    if source_payload.get("decision") != "accepted_default_off_broad_market_trend_persistence_notional":
        raise RuntimeError(f"Unexpected source decision: {source_payload.get('decision')}")

    before_metrics = source_payload["after_metrics"]
    control_metrics = control_payload["before_metrics"]
    baseline = prior._resimulate_source_baseline(source_payload)
    price_indexes = p35._index_by_date(baseline["prices"])
    variants = [
        _variant_payload(
            variant_name=name,
            high_cost_scalar=float(values["high_cost_scalar"]),
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            baseline_trades_by_window=baseline["trades_by_window"],
            prices=baseline["prices"],
            indexes=price_indexes,
            baseline_replay_parity_passed=baseline["parity_passed"],
        )
        for name, values in COST_HAIRCUT_SWEEP.items()
    ]
    selected = _choose_selected(variants)
    gate4_passed = bool(selected["gate4"]["passed"])
    status = "observed_only" if gate4_passed else "rejected"
    decision = (
        "observed_positive_broad_market_cost_liquidity_haircut_requires_shared_adapter"
        if gate4_passed
        else "rejected_broad_market_cost_liquidity_haircut"
    )

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
        "note": "No core filter was added; selected broad-market paper trades stay unchanged.",
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "default_off_paper_only": True,
        "research_replay_alters_paper_notional": True,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "promotion_blocker": (
            "If positive, implement the same cost/liquidity proxy through a "
            "shared default-off broad-market paper adapter before retention. "
            "This run does not create production/backtest behavior divergence "
            "because it does not promote the haircut."
        ),
    }
    baseline_replay_parity = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "passed": baseline["parity_passed"],
        "source_pnl_by_window": baseline["source_pnl_by_window"],
        "replayed_pnl_by_window": baseline["baseline_pnl_by_window"],
        "pnl_drift": baseline["pnl_drift"],
        "source_trade_count_by_window": baseline["source_trade_count_by_window"],
        "replayed_trade_count_by_window": baseline["baseline_trade_count_by_window"],
        "trade_count_drift": baseline["trade_count_drift"],
    }

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Accepted broad-market paper trades with high decision-date "
            "cost/liquidity proxy may have worse replacement value. A bounded "
            "paper-notional haircut on high expected round-trip cost candidates "
            "should improve risk-adjusted EV without changing discovery."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / risk allocation",
            "playbook_alignment": (
                "Directly follows the playbook's cost-aware allocation/data-edge "
                "surface using free OHLCV. It avoids sparse LLM soft-ranking, "
                "state-surface scalar retunes, and noisy ticker expansion."
            ),
            "why_now": (
                "Recent broad-market candidate-pool experiments repeatedly "
                "recommended cost-adjusted replacement value as the next distinct "
                "field after sector/industry confirmation variants failed Gate 4."
            ),
        },
        "history_check": {
            "nearby_experiments": [
                "exp-20260520-004 accepted broad-market trend-persistence notional support",
                "exp-20260527-901 rejected same-sector open-crowding haircut",
                "exp-20260527-021 rejected sector open-crowding support",
                "exp-20260527-022 rejected industry leadership breadth breakout",
                "exp-20260527-023 rejected Companyfacts-growth RS QQQ confirmation",
            ],
            "anti_repeat": (
                "Keeps accepted broad-market candidate set, rank profile, "
                "low-extension support, high-volatility support, trend-persistence "
                "support, hold days, entry slots, and universe fixed. Only the "
                "high expected-cost paper-notional scalar changes."
            ),
            "past_similar_experiment_result": (
                "No recorded experiment tested a decision-date cost/liquidity "
                "haircut on the accepted exp-20260520-004 broad-market sleeve."
            ),
        },
        "change_type": "default_off_paper_capital_allocation_scout",
        "changed_variable": "broad_market_high_expected_cost_notional_scalar",
        "single_causal_variable": (
            "paper-notional haircut scalar for already-selected broad-market "
            "trades whose decision-date OHLCV expected cost proxy is high"
        ),
        "component": "quant/experiments/exp_20260527_024_broad_market_cost_liquidity_haircut.py",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "rule_version": RULE_VERSION,
            "cost_proxy": {
                "inputs": [
                    "decision_date 20-session median dollar volume",
                    "source trade realized_volatility_20",
                ],
                "formula": (
                    "3 bps base + min(32, 80/sqrt(median_dollar_volume_20/1e6)) "
                    "+ min(42, realized_volatility_20*10000*0.08)"
                ),
                "high_threshold_bps": COST_BPS_HIGH_THRESHOLD,
                "lookahead_policy": (
                    "Uses OHLCV up to the trade decision date only; no future "
                    "window median or post-entry outcome data."
                ),
            },
            "sweep": COST_HAIRCUT_SWEEP,
            "selected_variant": selected["variant_name"],
            "selected_high_cost_scalar": selected["high_cost_scalar"],
            "candidate_count": len(baseline["candidate_tickers"]),
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
                "broad-market low-extension scalar",
                "broad-market high-volatility scalar",
                "broad-market trend-persistence scalar",
                "broad-market hold days",
                "broad-market active position cap",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": MIN_EV_IMPROVED_WINDOWS,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "minimum_selected_trades": p35.MIN_SELECTED_TRADES,
                "minimum_adjusted_trades": MIN_ADJUSTED_TRADES,
                "minimum_adjusted_windows": MIN_ADJUSTED_WINDOWS,
                "max_drawdown_worse": p35.MAX_DRAWDOWN_WORSE,
                "requires_baseline_replay_parity": True,
            },
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: {"start": row["start"], "end": row["end"], "snapshot": row["snapshot"]}
            for label, row in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; accepted "
            "exp-20260520-004 after_metrics are the before state; after state "
            "replays identical selected broad-market paper trades with one "
            "decision-date cost/liquidity paper-notional haircut variable."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": SOURCE_EXPERIMENT_ID,
            "baseline_artifact": _repo_rel(SOURCE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
            "baseline_replay_parity": baseline_replay_parity,
            "known_measurement_boundary": (
                "Historical replay uses the frozen exp-20260520-004 candidate "
                "universe. The tested haircut is not promoted into production "
                "or default-off paper behavior in this commit."
            ),
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": selected["gate4"],
        "baseline_replay_parity": baseline_replay_parity,
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
            "high_cost_scalar": selected["high_cost_scalar"],
            "cost_bps_high_threshold": COST_BPS_HIGH_THRESHOLD,
            "selected_trade_count": selected["selected_trade_count"],
            "adjusted_trade_count": selected["adjusted_trade_count"],
            "adjusted_windows": selected["adjusted_windows"],
            "pre_adjusted_pnl": selected["pre_adjusted_pnl"],
            "adjusted_pnl": selected["adjusted_pnl"],
            "notional_removed": selected["notional_removed"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "event_risk": selected["event_risk"],
            "cost_bucket_counts": selected["cost_bucket_counts"],
            "cost_bucket_pnl": selected["cost_bucket_pnl"],
            "adjusted_cost_bucket_counts": selected["adjusted_cost_bucket_counts"],
            "adjusted_trades_sample": selected["adjusted_trades_sample"],
        },
        "broad_market_sleeve": selected["broad_market_sleeve"],
        "llm_metrics": {
            "changed": False,
            "reason": "This run avoids sparse LLM soft-ranking and does not alter LLM prompts or decisions.",
        },
        "production_impact": production_impact,
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital/risk allocation: high expected transaction-cost/liquidity "
                "broad-market paper trades may deserve a bounded notional haircut."
            ),
            "2_past_similar_experiments": (
                "exp-20260520-004 was accepted; exp-20260527-901/021/022/023 "
                "tested adjacent broad-market sector/industry/fundamental "
                "confirmations and failed or were rejected. No logged run tested "
                "this decision-date cost/liquidity scalar."
            ),
            "3_single_variable": (
                "Only high expected-cost notional scalar changes; candidate "
                "eligibility, ranking, existing support scalars, hold, slots, and "
                "universe remain fixed."
            ),
            "4_acceptance": (
                "Gate 4 requires positive aggregate EV/PnL, all 3 windows EV-"
                "positive, no EV/PnL regression windows, >=8 adjusted trades "
                "across all 3 windows, concentration guard, <=0.5pp drawdown "
                "worsening, and baseline replay parity."
            ),
            "5_reproducibility": (
                "Script, JSON artifact, ticket, markdown artifact, and docs JSONL "
                "record windows, source artifact, sweep parameters, Gate 1-4, and "
                "selected result."
            ),
        },
        "interpretation": (
            "Cost/liquidity is tested as a capital allocation layer on the "
            "accepted broad-market paper sleeve. Because the current run does "
            "not promote a shared adapter, positive evidence is only an observed "
            "lead and cannot affect production."
        ),
        "rejection_reason": None if gate4_passed else "Best cost/liquidity haircut variant failed Gate 4.",
        "next_evidence_needed": (
            "If rejected, do not retry adjacent cost thresholds/scalars without "
            "new forward closed outcomes. Next broad-market alpha should use a "
            "distinct candidate-pool expansion or data edge."
            if not gate4_passed
            else "Implement a shared decision-date cost/liquidity default-off "
            "broad-market paper adapter plus parity tests before retaining this "
            "positive capital-allocation rule."
        ),
        "why_not_other_changes": [
            "No VCP/VBB threshold or rank-profile retune.",
            "No state-surface notional scalar retune.",
            "No LLM soft-ranking or prompt change.",
            "No noisy ticker expansion.",
            "No core/live production order path change.",
        ],
        "known_risks": [
            "The cost proxy is a heuristic, not realized bid/ask spread.",
            "Positive replay would still need shared production/backtest parity before retention.",
            "This does not expand candidate discovery; it only tests cost-aware allocation.",
        ],
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "doc_ticket": _repo_rel(DOC_TICKET_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
            "source": _repo_rel(SOURCE_JSON),
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
        "baseline_replay_parity": payload["baseline_replay_parity"],
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
        "baseline_replay_parity": payload["baseline_replay_parity"],
        "production_impact": payload["production_impact"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "related_files": payload["related_files"],
    }
    _write_json(TICKET_JSON, ticket)
    _write_json(DOC_TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "selected_variant": payload["selected_variant"]["variant_name"],
                    "gate4": payload["gate4"],
                    "baseline_replay_parity": payload["baseline_replay_parity"],
                    "aggregate_ev_delta": payload["delta_metrics"]["aggregate_ev_delta"],
                    "aggregate_pnl_delta": payload["delta_metrics"]["aggregate_pnl_delta"],
                    "production_impact": payload["production_impact"],
                    "output": payload["related_files"]["output"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
