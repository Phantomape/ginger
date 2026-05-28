"""exp-20260528-001: broad-market repeat-leadership support.

Replay-only alpha search for the accepted default-off broad-market leadership
paper sleeve. The single causal variable is a bounded paper-notional scalar for
selected candidates whose ticker already had a prior selected broad-market hit
inside the same canonical replay window.

No core entries, exits, sizing, ranking, LLM/news decisions, production orders,
or shared paper adapter behavior are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260528-001"
EXPERIMENT_SLUG = "broad_market_repeat_leadership_support"
SOURCE_EXPERIMENT_ID = "exp-20260520-004"
SOURCE_SLUG = "broad_market_trend_persistence_notional"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
import exp_20260520_004_broad_market_trend_persistence_notional as e004  # noqa: E402
from broad_market_paper_sleeve import (  # noqa: E402
    backtest_trade_from_feature,
    build_broad_market_feature,
    candidate_passes_profile,
    select_broad_market_features,
)


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

PROFILE_CONFIG = {
    **e004.PROFILE_CONFIG,
    "trend_persistence_positive_day_ratio_20_min": 0.55,
    "trend_persistence_notional_scalar": 1.15,
}

REPEAT_SUPPORT_SWEEP: "OrderedDict[str, float]" = OrderedDict()
REPEAT_SUPPORT_SWEEP["repeat_scalar_1p00_baseline_replay"] = 1.00
for scalar in (1.025, 1.05, 1.075, 1.10, 1.15, 1.25, 1.50):
    scalar_text = f"{scalar:.3f}".rstrip("0").rstrip(".").replace(".", "p")
    REPEAT_SUPPORT_SWEEP[f"repeat_scalar_{scalar_text}"] = scalar

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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _trade_key(trade: dict[str, Any]) -> tuple[str, str, str]:
    return (str(trade["window"]), str(trade["decision_date"]), str(trade["ticker"]))


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


def _scale_repeat_trade(trade: dict[str, Any], scalar: float) -> dict[str, Any]:
    if scalar == 1.0:
        trade["repeat_leadership_support_applied"] = False
        trade["repeat_leadership_notional_scalar"] = scalar
        return trade
    original_notional = float(trade["notional"])
    original_shares = float(trade["shares"])
    original_pnl = float(trade["pnl"])
    adjusted_notional = round(original_notional * scalar, 2)
    trade["pre_repeat_support_notional"] = original_notional
    trade["pre_repeat_support_shares"] = original_shares
    trade["pre_repeat_support_pnl"] = original_pnl
    trade["repeat_leadership_support_applied"] = True
    trade["repeat_leadership_notional_scalar"] = scalar
    trade["notional"] = adjusted_notional
    trade["shares"] = round(original_shares * scalar, 8)
    trade["pnl"] = round(original_pnl * scalar, 2)
    return trade


def _trade_rows(trades: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
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
                "ret20_excess_spy": trade["ret20_excess_spy"],
                "ret5": trade.get("ret5"),
                "ret60": trade["ret60"],
                "near_high_60": trade["near_high_60"],
                "volume_ratio_20": trade["volume_ratio_20"],
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "freshness_bucket": trade.get("freshness_bucket"),
                "prior_selected_hit_seen": trade.get("prior_selected_hit_seen"),
                "repeat_leadership_support_applied": trade.get("repeat_leadership_support_applied"),
                "repeat_leadership_notional_scalar": trade.get("repeat_leadership_notional_scalar"),
                "notional": trade.get("notional"),
                "pre_repeat_support_notional": trade.get("pre_repeat_support_notional"),
                "pre_repeat_support_pnl": trade.get("pre_repeat_support_pnl"),
            }
        )
    return rows


def _simulate_window(
    *,
    label: str,
    repeat_scalar: float,
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
) -> dict[str, Any]:
    spec = WINDOWS[label]
    days = p35._trading_days(prices, spec["start"], spec["end"])
    spy_rows = prices.get("SPY") or []
    spy_index = indexes.get("SPY") or {}
    active: list[dict[str, str]] = []
    seen_tickers: set[str] = set()
    trades: list[dict[str, Any]] = []
    daily_counts: dict[str, int] = {}
    repeat_candidates_by_day: dict[str, int] = {}
    repeat_selected_by_day: dict[str, int] = {}

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = int(PROFILE_CONFIG["max_active_positions"]) - len(active)
        if capacity <= 0:
            continue

        active_tickers = {row["ticker"] for row in active}
        features: list[dict[str, Any]] = []
        repeat_candidates = 0
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
                if str(feature["ticker"]) in seen_tickers:
                    repeat_candidates += 1
                features.append(feature)

        selected = select_broad_market_features(
            features,
            capacity=capacity,
            config=PROFILE_CONFIG,
        )
        repeat_selected = 0
        for rank, feature in enumerate(selected, start=1):
            ticker = str(feature["ticker"])
            is_repeat = ticker in seen_tickers
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
            trade["freshness_bucket"] = "repeat_hit" if is_repeat else "first_hit"
            trade["prior_selected_hit_seen"] = is_repeat
            trade["repeat_leadership_rule_active"] = True
            if is_repeat:
                repeat_selected += 1
                _scale_repeat_trade(trade, repeat_scalar)
            else:
                trade["repeat_leadership_support_applied"] = False
                trade["repeat_leadership_notional_scalar"] = repeat_scalar
            trades.append(trade)
            active.append({"ticker": ticker, "exit_date": trade["exit_date"]})
            active_tickers.add(ticker)
            seen_tickers.add(ticker)
        daily_counts[day] = len(features)
        repeat_candidates_by_day[day] = repeat_candidates
        repeat_selected_by_day[day] = repeat_selected

    return {
        "window": label,
        "trades": trades,
        "candidate_signal_days": sum(1 for count in daily_counts.values() if count > 0),
        "candidate_signal_count": sum(daily_counts.values()),
        "max_daily_candidate_count": max(daily_counts.values()) if daily_counts else 0,
        "repeat_candidate_signal_count": sum(repeat_candidates_by_day.values()),
        "repeat_selected_trade_count": sum(repeat_selected_by_day.values()),
        "sample_repeat_candidate_counts": dict(list(repeat_candidates_by_day.items())[:20]),
        "sample_repeat_selected_counts": dict(list(repeat_selected_by_day.items())[:20]),
    }


def _freshness_bucket_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    by_bucket: dict[str, list[dict[str, Any]]] = {"first_hit": [], "repeat_hit": []}
    for trade in trades:
        by_bucket.setdefault(str(trade.get("freshness_bucket") or "unknown"), []).append(trade)
    for bucket, rows in sorted(by_bucket.items()):
        pnl = sum(float(row.get("pnl") or 0.0) for row in rows)
        returns = [float(row.get("net_return_pct") or 0.0) for row in rows]
        out[bucket] = {
            "trade_count": len(rows),
            "total_pnl": round(pnl, 2),
            "avg_pnl": round(pnl / len(rows), 2) if rows else None,
            "avg_return_pct": round(sum(returns) / len(returns), 6) if returns else None,
            "win_rate": round(sum(1 for row in rows if float(row.get("pnl") or 0.0) > 0) / len(rows), 6)
            if rows
            else None,
        }
    return out


def _window_sleeve_summary(scout: dict[str, Any]) -> dict[str, Any]:
    base = p35._window_sleeve_summary(scout["trades"], scout)
    adjusted = [row for row in scout["trades"] if row.get("repeat_leadership_support_applied")]
    base["repeat_candidate_signal_count"] = scout["repeat_candidate_signal_count"]
    base["repeat_selected_trade_count"] = scout["repeat_selected_trade_count"]
    base["repeat_support_adjusted_trade_count"] = len(adjusted)
    base["repeat_support_adjusted_pnl"] = round(
        sum(float(row.get("pnl") or 0.0) for row in adjusted),
        2,
    )
    base["freshness_buckets"] = _freshness_bucket_summary(scout["trades"])
    base["sample_trades"] = _trade_rows(scout["trades"], limit=25)
    return base


def _variant_payload(
    *,
    variant_name: str,
    repeat_scalar: float,
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
            repeat_scalar=repeat_scalar,
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
        sleeve[label] = _window_sleeve_summary(scout)

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    adjusted = [row for row in all_trades if row.get("repeat_leadership_support_applied")]
    adjusted_windows = sorted({row["window"] for row in adjusted})
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = p35._single_ticker_positive_share(all_trades)
    top5_share = p35._top5_positive_share(all_trades)
    relative_ev_improvement = float(delta["aggregate_ev_delta_pct"] or 0.0)
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
    materiality_guard_passed = relative_ev_improvement >= MIN_RELATIVE_EV_IMPROVEMENT
    gate4_passed = bool(
        repeat_scalar != 1.0
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
        and materiality_guard_passed
    )
    return {
        "variant_name": variant_name,
        "repeat_scalar": repeat_scalar,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "adjusted_trade_count": len(adjusted),
        "adjusted_windows": adjusted_windows,
        "adjusted_pnl": round(sum(float(row.get("pnl") or 0.0) for row in adjusted), 2),
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": p35._event_risk(all_trades),
        "freshness_buckets": _freshness_bucket_summary(all_trades),
        "selected_trade_keys": sorted("|".join(_trade_key(row)) for row in all_trades),
        "selected_trades_sample": _trade_rows(all_trades, limit=80),
        "adjusted_trades_sample": _trade_rows(adjusted, limit=60),
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta": delta["aggregate_ev_delta"],
            "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
            "relative_ev_improvement": relative_ev_improvement,
            "minimum_relative_ev_improvement": MIN_RELATIVE_EV_IMPROVEMENT,
            "materiality_guard_passed": materiality_guard_passed,
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


def _choose_selected(variants: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in variants if row["gate4"]["passed"]]
    pool = passing or [row for row in variants if row["repeat_scalar"] != 1.0]
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
            "repeat_scalar": row["repeat_scalar"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "selected_ticker_count": row["selected_ticker_count"],
            "adjusted_trade_count": row["adjusted_trade_count"],
            "adjusted_windows": row["adjusted_windows"],
            "aggregate_ev_delta": row["delta_metrics"]["aggregate_ev_delta"],
            "relative_ev_improvement": row["gate4"]["relative_ev_improvement"],
            "aggregate_pnl_delta": row["delta_metrics"]["aggregate_pnl_delta"],
            "windows_ev_improved": row["gate4"]["windows_ev_improved"],
            "windows_ev_regressed": row["gate4"]["windows_ev_regressed"],
            "windows_pnl_regressed": row["gate4"]["windows_pnl_regressed"],
            "max_drawdown_worse_max": row["gate4"]["max_drawdown_worse_max"],
            "single_ticker_positive_share": row["single_ticker_positive_share"],
            "top5_positive_share": row["top5_positive_share"],
            "materiality_guard_passed": row["gate4"]["materiality_guard_passed"],
        }
        for row in variants
    ]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Repeat-Leadership Support",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: paper-notional scalar for selected broad-market candidates whose ticker already had a prior selected hit in the same canonical replay window.",
        "",
        "## Sweep",
        "",
        "| Variant | Gate 4 | Scalar | Adjusted | dEV | dPnL | Rel EV | EV +/- | PnL Regr | Max DD Drift |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant} | {gate} | {scalar:.3f} | {adjusted} | {ev:+.4f} | ${pnl:+,.2f} | {rel:+.2%} | {wi}/{wr} | {pr} | {dd:+.4%} |".format(
                variant=row["variant_name"],
                gate="PASS" if row["passed"] else "FAIL",
                scalar=float(row["repeat_scalar"]),
                adjusted=row["adjusted_trade_count"],
                ev=float(row["aggregate_ev_delta"] or 0.0),
                pnl=float(row["aggregate_pnl_delta"] or 0.0),
                rel=float(row["relative_ev_improvement"] or 0.0),
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
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Repro",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260528_001_broad_market_repeat_leadership_support.py",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def _experiment_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
    }


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
    control_metrics = control_payload["before_metrics"]
    before_metrics = source_payload["after_metrics"]
    candidate_universe = {
        **source_payload.get("candidate_universe", {}),
        "source": "frozen_source_artifact_candidate_universe",
    }
    if not candidate_universe.get("tickers"):
        candidate_universe = p35._candidate_universe(set(p35._load_tradeable_universe()["excluded_tradeable_universe"]))
    prices = p35._load_price_rows(candidate_universe["tickers"])
    indexes = p35._index_by_date(prices)

    variants = [
        _variant_payload(
            variant_name=name,
            repeat_scalar=scalar,
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            candidate_tickers=candidate_universe["tickers"],
            prices=prices,
            indexes=indexes,
        )
        for name, scalar in REPEAT_SUPPORT_SWEEP.items()
    ]

    baseline_replay = next(row for row in variants if row["repeat_scalar"] == 1.0)
    baseline_replay_parity = {
        "passed": abs(float(baseline_replay["delta_metrics"]["aggregate_ev_delta"])) <= 0.0001
        and abs(float(baseline_replay["delta_metrics"]["aggregate_pnl_delta"])) <= 0.01,
        "aggregate_ev_delta": baseline_replay["delta_metrics"]["aggregate_ev_delta"],
        "aggregate_pnl_delta": baseline_replay["delta_metrics"]["aggregate_pnl_delta"],
        "by_window": baseline_replay["delta_metrics"]["by_window"],
    }
    selected = _choose_selected(variants)
    gate4_passed = bool(selected["gate4"]["passed"] and baseline_replay_parity["passed"])
    observed_positive = gate4_passed
    decision = (
        "observed_positive_broad_market_repeat_leadership_support_requires_shared_adapter"
        if observed_positive
        else "rejected_broad_market_repeat_leadership_support"
    )
    status = "observed_only" if observed_positive else "rejected"
    aggregate_before = p35._aggregate(before_metrics)
    aggregate_after = p35._aggregate(selected["after_metrics"])
    gate3 = {
        "signals_generated": {label: before_metrics[label].get("signals_generated") for label in WINDOWS},
        "signals_survived": {label: before_metrics[label].get("signals_survived") for label in WINDOWS},
        "survival_rate": {label: before_metrics[label].get("survival_rate") for label in WINDOWS},
        "survival_rate_min": aggregate_before["survival_rate_min"],
        "passed": aggregate_before["survival_rate_min"] >= 0.05,
        "note": "No core filter was added; broad-market sleeve remains default-off paper only.",
    }
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "default_off_paper_only": True,
        "trade_enabled": False,
        "live_order_path_changed": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_exits": False,
        "alters_orders": False,
        "alters_sizing": False,
        "promotion_requirement": "Positive evidence is not retained until the shared broad-market paper adapter can expose identical append-only repeat-hit state and parity checks.",
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Broad-market paper candidates that repeat after a prior selected hit "
            "may represent persistent leadership rather than decay; a bounded "
            "repeat-hit paper-notional support scalar may improve replacement "
            "value without adding noisy tickers."
        ),
        "change_summary": "Replay-only repeat-hit paper-notional support on the accepted broad-market paper sleeve.",
        "change_type": "default_off_paper_risk_allocation",
        "mechanism_family": "leadership_persistence_candidate_pool",
        "trial_family": "broad_market_repeat_leadership_support",
        "trial_variant_id": f"repeat_scalar_{selected['repeat_scalar']:.3f}".replace(".", "p"),
        "changed_variable": "broad_market_repeat_hit_notional_scalar",
        "prior_trial_count": 5,
        "nearby_prior_experiments": [
            "exp-20260520-004",
            "exp-20260527-021",
            "exp-20260527-024",
            "exp-20260527-025",
            "exp-20260527-026",
        ],
        "multiple_testing_risk_bucket": "high_state_surface_scalar",
        "new_evidence_type": "append_only_paper_ledger_repeat_hit_state",
        "anti_js": "No JavaScript was used.",
        "alpha_hypothesis": {
            "category": "candidate_pool / risk_allocation",
            "playbook_alignment": (
                "Uses the prior first-hit rejection as evidence that repeat "
                "leadership may be useful, while keeping the broad-market "
                "candidate pool frozen instead of adding noisy tickers."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "risk_allocation/candidate_pool: repeat broad-market hits may deserve more paper notional if they indicate persistent leadership.",
            "2_past_similar_experiments": "exp-20260527-026 removed repeat hits and regressed all three windows; exp-20260520-004 accepted trend-persistence notional support.",
            "3_single_variable": "broad_market_repeat_hit_notional_scalar",
            "4_acceptance": "Three-window Gate 4 requires positive aggregate EV/PnL, all 3 EV-improved windows, no EV/PnL-regressed windows, >=10% relative EV improvement, drawdown/concentration/sample guards, and baseline replay parity.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260528_001_broad_market_repeat_leadership_support.py",
        },
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "candidate_count": len(candidate_universe["tickers"]),
            "candidate_universe_source": candidate_universe.get("source"),
            "profile_config": PROFILE_CONFIG,
            "repeat_support_sweep": REPEAT_SUPPORT_SWEEP,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core entries",
                "core exits",
                "core sizing",
                "portfolio heat",
                "LLM/news decisions",
                "live/default orders",
                "broad-market profile thresholds",
                "broad-market rank-notional profile",
                "broad-market existing support scalars",
                "broad-market hold days",
                "broad-market active position cap",
                "broad-market candidate universe",
            ],
        },
        "date_range": source_payload["date_range"],
        "before_metrics": _compact_metrics(before_metrics),
        "after_metrics": _compact_metrics(selected["after_metrics"]),
        "aggregate_before": aggregate_before,
        "aggregate_after": aggregate_after,
        "delta_metrics": selected["delta_metrics"],
        "expected_value_score_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_ev_delta"],
            **{
                label: selected["delta_metrics"]["by_window"][label]["expected_value_score"]
                for label in WINDOWS
            },
        },
        "total_pnl_delta": {
            "aggregate": selected["delta_metrics"]["aggregate_pnl_delta"],
            **{label: selected["delta_metrics"]["by_window"][label]["total_pnl"] for label in WINDOWS},
        },
        "gate1": {
            "passed": bool(baseline_replay_parity["passed"]),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows; accepted exp-20260520-004 after_metrics are the before state.",
            "source_artifact": _repo_rel(SOURCE_JSON),
            "control_artifact": _repo_rel(CONTROL_JSON),
            "before_aggregate": aggregate_before,
            "baseline_replay_parity": baseline_replay_parity,
        },
        "gate2": {
            **gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "broad-market paper selected ticker history from append-only ledger state",
                "decision-date OHLCV rows",
            ],
        },
        "gate3": gate3,
        "gate4": {
            **selected["gate4"],
            "baseline_replay_parity_passed": baseline_replay_parity["passed"],
            "promotion_blocked_without_shared_adapter": observed_positive,
        },
        "sweep_summary": _sweep_summary(variants),
        "selected_variant": selected,
        "production_impact": production_impact,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "interpretation": (
            "Repeat-hit support is retainable only if it clears the stricter "
            "state-surface scalar bar. A positive replay result remains "
            "non-promotable until shared adapter parity is implemented; this "
            "run changes no production or backtest behavior."
        ),
        "rejection_reason": None
        if observed_positive
        else (
            "Baseline replay parity failed; current code/universe cannot reproduce the accepted broad-market source artifact."
            if not baseline_replay_parity["passed"]
            else "Repeat-hit notional support failed the strict three-window broad-market Gate 4."
        ),
        "next_retry_requires": [
            "new forward broad-market paper ledger rows rather than adjacent scalar retunes",
            "shared adapter repeat-hit state with explicit warmup before any positive promotion",
            "candidate-pool expansion evidence from free data if repeat support remains non-material",
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


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, _experiment_log_payload(payload))
    _write_json(DOC_TICKET_JSON, _experiment_log_payload(payload))
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
