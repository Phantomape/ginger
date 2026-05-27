"""exp-20260527-026: broad-market first-hit leadership decay.

Replay-only alpha search for the accepted default-off broad-market leadership
paper sleeve. The single causal variable is candidate freshness: after a ticker
has already been selected once in a canonical window, later same-ticker
broad-market candidates are skipped so the sleeve tests whether fresh
leadership episodes beat repeat leadership episodes.

No core entries, exits, sizing, ranking, LLM/news decisions, production orders,
or shared paper adapter behavior are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260527-026"
EXPERIMENT_SLUG = "broad_market_first_hit_decay"
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

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "accepted_repeat_allowed",
            {"skip_seen_tickers": False},
        ),
        (
            "fresh_first_hit_only",
            {"skip_seen_tickers": True},
        ),
    ]
)

MIN_REPLACED_TRADES = 4
MIN_REPLACED_WINDOWS = 2
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


def _trade_key(trade: dict[str, Any]) -> tuple[str, str, str]:
    return (str(trade["window"]), str(trade["decision_date"]), str(trade["ticker"]))


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {key: value for key, value in row.items() if key != "combined_equity_curve"}
        for label, row in metrics.items()
    }


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
                "suppressed_repeat_candidates": trade.get("suppressed_repeat_candidates", 0),
                "notional": trade.get("notional"),
            }
        )
    return rows


def _simulate_window(
    *,
    label: str,
    skip_seen_tickers: bool,
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
    suppressed_counts: dict[str, int] = {}

    for day in days:
        active = [row for row in active if row["exit_date"] > day]
        capacity = int(PROFILE_CONFIG["max_active_positions"]) - len(active)
        if capacity <= 0:
            continue

        active_tickers = {row["ticker"] for row in active}
        features: list[dict[str, Any]] = []
        suppressed = 0
        for ticker in candidate_tickers:
            if ticker in active_tickers:
                continue
            if skip_seen_tickers and ticker in seen_tickers:
                suppressed += 1
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
            ticker = str(feature["ticker"])
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
            trade["freshness_bucket"] = "first_hit" if ticker not in seen_tickers else "repeat_hit"
            trade["freshness_rule_active"] = skip_seen_tickers
            trade["suppressed_repeat_candidates"] = suppressed
            trades.append(trade)
            active.append({"ticker": ticker, "exit_date": trade["exit_date"]})
            active_tickers.add(ticker)
            seen_tickers.add(ticker)
        daily_counts[day] = len(features)
        suppressed_counts[day] = suppressed

    return {
        "window": label,
        "trades": trades,
        "candidate_signal_days": sum(1 for count in daily_counts.values() if count > 0),
        "candidate_signal_count": sum(daily_counts.values()),
        "max_daily_candidate_count": max(daily_counts.values()) if daily_counts else 0,
        "suppressed_repeat_candidate_count": sum(suppressed_counts.values()),
        "sample_suppressed_repeat_counts": dict(list(suppressed_counts.items())[:20]),
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
    base["suppressed_repeat_candidate_count"] = scout["suppressed_repeat_candidate_count"]
    base["freshness_buckets"] = _freshness_bucket_summary(scout["trades"])
    base["sample_trades"] = _trade_rows(scout["trades"], limit=25)
    return base


def _variant_payload(
    *,
    variant_name: str,
    variant: dict[str, Any],
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    candidate_tickers: list[str],
    prices: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, int]],
    identity_keys: set[tuple[str, str, str]] | None,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []

    for label, spec in WINDOWS.items():
        scout = _simulate_window(
            label=label,
            skip_seen_tickers=bool(variant["skip_seen_tickers"]),
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

    keys = {_trade_key(row) for row in all_trades}
    if identity_keys is None:
        replaced_count = 0
        replaced_windows: list[str] = []
    else:
        replacement_keys = keys - identity_keys
        replaced_count = len(replacement_keys)
        replaced_windows = sorted({key[0] for key in replacement_keys})

    delta = p35._aggregate_delta(before_metrics, after_metrics)
    selected_windows = sum(1 for row in sleeve.values() if row["trade_count"] > 0)
    single_share = p35._single_ticker_positive_share(all_trades)
    top5_share = p35._top5_positive_share(all_trades)
    relative_ev_improvement = float(delta["aggregate_ev_delta_pct"] or 0.0)
    sample_guard_passed = len(all_trades) >= p35.MIN_SELECTED_TRADES
    replacement_guard_passed = (
        replaced_count >= MIN_REPLACED_TRADES
        and len(replaced_windows) >= MIN_REPLACED_WINDOWS
    )
    window_guard_passed = selected_windows >= p35.MIN_SELECTED_WINDOWS
    concentration_guard_passed = (
        (single_share is None or single_share <= p35.MAX_SINGLE_TICKER_POSITIVE_SHARE)
        and (top5_share is None or top5_share <= p35.MAX_TOP5_POSITIVE_SHARE)
    )
    drawdown_guard_passed = delta["max_drawdown_worse_max"] <= p35.MAX_DRAWDOWN_WORSE
    materiality_guard_passed = relative_ev_improvement >= MIN_RELATIVE_EV_IMPROVEMENT
    gate4_passed = bool(
        variant_name != "accepted_repeat_allowed"
        and delta["aggregate_ev_delta"] > 0
        and delta["aggregate_pnl_delta"] > 0
        and delta["windows_ev_improved"] >= MIN_EV_IMPROVED_WINDOWS
        and delta["windows_ev_regressed"] == 0
        and delta["windows_pnl_regressed"] == 0
        and sample_guard_passed
        and replacement_guard_passed
        and window_guard_passed
        and concentration_guard_passed
        and drawdown_guard_passed
        and materiality_guard_passed
    )
    return {
        "variant_name": variant_name,
        "variant": variant,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "broad_market_sleeve": sleeve,
        "selected_trade_count": len(all_trades),
        "selected_windows": selected_windows,
        "selected_ticker_count": len({row["ticker"] for row in all_trades}),
        "replaced_trade_count": replaced_count,
        "replaced_windows": replaced_windows,
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": p35._event_risk(all_trades),
        "freshness_buckets": _freshness_bucket_summary(all_trades),
        "selected_trade_keys": sorted("|".join(key) for key in keys),
        "selected_trades_sample": _trade_rows(all_trades, limit=80),
        "replacement_trades_sample": [
            row
            for row in _trade_rows(all_trades, limit=250)
            if _trade_key(row) not in (identity_keys or set())
        ][:50],
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
            "replaced_trade_count": replaced_count,
            "minimum_replaced_trades": MIN_REPLACED_TRADES,
            "replaced_windows": replaced_windows,
            "minimum_replaced_windows": MIN_REPLACED_WINDOWS,
            "replacement_guard_passed": replacement_guard_passed,
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


def _sweep_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant_name": row["variant_name"],
            "skip_seen_tickers": row["variant"]["skip_seen_tickers"],
            "passed": row["gate4"]["passed"],
            "selected_trade_count": row["selected_trade_count"],
            "selected_ticker_count": row["selected_ticker_count"],
            "replaced_trade_count": row["replaced_trade_count"],
            "replaced_windows": row["replaced_windows"],
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
        f"# {EXPERIMENT_ID} Broad-Market First-Hit Leadership Decay",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: skip repeat same-ticker broad-market paper candidates after the ticker's first selected hit in the same canonical replay window.",
        "",
        "## Sweep",
        "",
        "| Variant | Passed | EV delta | PnL delta | Windows EV +/- | Replaced | Trades | Tickers | Max DD drift |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["sweep_summary"]:
        lines.append(
            "| {variant_name} | {passed} | {aggregate_ev_delta:.4f} | ${aggregate_pnl_delta:,.2f} | {windows_ev_improved}/{windows_ev_regressed} | {replaced_trade_count} | {selected_trade_count} | {selected_ticker_count} | {max_drawdown_worse_max:.4f} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Gate 4",
            "",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Repro",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260527_026_broad_market_first_hit_decay.py",
            "```",
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

    variants: list[dict[str, Any]] = []
    identity_keys: set[tuple[str, str, str]] | None = None
    for name, variant in VARIANTS.items():
        row = _variant_payload(
            variant_name=name,
            variant=variant,
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            candidate_tickers=candidate_universe["tickers"],
            prices=prices,
            indexes=indexes,
            identity_keys=identity_keys,
        )
        variants.append(row)
        if name == "accepted_repeat_allowed":
            identity_keys = {
                tuple(str(part) for part in key.split("|"))
                for key in row["selected_trade_keys"]
            }

    baseline_replay = next(row for row in variants if row["variant_name"] == "accepted_repeat_allowed")
    baseline_replay_parity = {
        "passed": abs(float(baseline_replay["delta_metrics"]["aggregate_ev_delta"])) <= 0.0001
        and abs(float(baseline_replay["delta_metrics"]["aggregate_pnl_delta"])) <= 0.01,
        "aggregate_ev_delta": baseline_replay["delta_metrics"]["aggregate_ev_delta"],
        "aggregate_pnl_delta": baseline_replay["delta_metrics"]["aggregate_pnl_delta"],
        "by_window": baseline_replay["delta_metrics"]["by_window"],
    }
    selected = next(row for row in variants if row["variant_name"] == "fresh_first_hit_only")
    accepted = bool(selected["gate4"]["passed"] and baseline_replay_parity["passed"])
    decision = (
        "promising_replay_only_broad_market_first_hit_decay"
        if accepted
        else "rejected_broad_market_first_hit_decay"
    )
    status = "observed_only" if accepted else "rejected"
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
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "promotion_requirement": "If positive, implement this freshness state in the shared broad-market paper adapter with append-only ledger warmup before any retention.",
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "Broad-market leadership episodes may decay after the first selected "
            "paper hit in a ticker; replacing repeat same-ticker hits with fresh "
            "leaders should improve replacement value if leadership persistence "
            "is broad rather than single-name crowded."
        ),
        "change_summary": "Replay-only first-hit freshness selection on the accepted broad-market paper sleeve.",
        "change_type": "default_off_paper_candidate_selection",
        "mechanism_family": "leadership_persistence_candidate_pool",
        "trial_family": "broad_market_first_hit_leadership_decay",
        "trial_variant_id": "fresh_first_hit_only_v1",
        "changed_variable": "broad_market_fresh_first_hit_only_candidate_selection",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260520-004",
            "exp-20260527-021",
            "exp-20260527-024",
            "exp-20260527-025",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "append_only_paper_ledger_candidate_freshness_state",
        "anti_js": "No JavaScript was used.",
        "alpha_hypothesis": {
            "category": "candidate_pool / ranking",
            "playbook_alignment": (
                "Tests leadership persistence and pattern decay after first hit, "
                "not another fixed notional scalar, ticker hack, or threshold retune."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": "ranking/candidate_pool: broad-market repeat leadership may decay after the first selected paper hit.",
            "2_past_similar_experiments": "Recent broad-market cost/liquidity and idiosyncratic residual tests were rejected; no prior broad-market first-hit ledger freshness test was found.",
            "3_single_variable": "broad_market_fresh_first_hit_only_candidate_selection",
            "4_acceptance": "Three-window Gate 4 requires positive aggregate EV/PnL, all 3 EV-improved windows, no EV/PnL-regressed windows, >=10% relative EV improvement, drawdown/concentration/sample guards.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260527_026_broad_market_first_hit_decay.py",
        },
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "candidate_count": len(candidate_universe["tickers"]),
            "candidate_universe_source": candidate_universe.get("source"),
            "profile_config": PROFILE_CONFIG,
            "variants": VARIANTS,
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
                "broad-market support scalars",
                "broad-market hold days",
                "broad-market active position cap",
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
        "gate4": selected["gate4"],
        "sweep_summary": _sweep_summary(variants),
        "selected_variant": selected,
        "production_impact": production_impact,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "interpretation": (
            "First-hit freshness is retained only if it materially improves all "
            "three windows. A positive replay result remains non-promotable until "
            "the shared default-off broad-market adapter can expose the same "
            "append-only freshness state with warmup; this run changes no "
            "production or backtest behavior."
        ),
        "rejection_reason": None
        if accepted
        else (
            "Baseline replay parity failed; current code/universe cannot reproduce the accepted broad-market source artifact."
            if not baseline_replay_parity["passed"]
            else "First-hit freshness failed the strict three-window broad-market Gate 4."
        ),
        "next_retry_requires": [
            "closed forward broad-market replacement-value rows",
            "shared paper-ledger freshness state with explicit warmup",
            "no adjacent cooldown/lookback retune on the frozen sample",
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
    _append_jsonl_once(EXPERIMENT_LOG, _experiment_log_payload(payload))
    print(json.dumps(payload["gate4"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
