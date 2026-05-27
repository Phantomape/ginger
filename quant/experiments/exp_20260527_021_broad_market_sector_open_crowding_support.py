"""exp-20260527-021: broad-market sector open-crowding support.

Alpha search. Uses the accepted exp-20260520-004 broad-market paper sleeve
and the accepted exp-20260525-038 sector map to test one causal variable:
whether already-selected broad-market paper trades deserve higher paper
notional when a same-sector broad-market paper position is already open.

This does not change core signal generation, ranking, exits, live orders,
LLM/news decisions, or production default-off paper behavior. Positive replay
evidence would still require a shared default-off adapter before promotion.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260527-021"
EXPERIMENT_SLUG = "broad_market_sector_open_crowding_support"
SOURCE_EXPERIMENT_ID = "exp-20260520-004"
SOURCE_SLUG = "broad_market_trend_persistence_notional"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"
SECTOR_MAP_EXPERIMENT_ID = "exp-20260525-038"
PRIOR_CROWDING_EXPERIMENT_ID = "exp-20260527-901"
RULE_VERSION = "broad_market_sector_open_crowding_support_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260527_901_broad_market_sector_open_crowding_haircut as prior  # noqa: E402


p35 = prior.p35
WINDOWS = prior.WINDOWS
SOURCE_JSON = prior.SOURCE_JSON
CONTROL_JSON = prior.CONTROL_JSON
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SUPPORT_SWEEP: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            "baseline_no_sector_open_crowding_support",
            {"min_active_same_sector": 1, "support_scalar": 1.00},
        ),
        (
            "same_sector_active_gte_1_scalar_1p05",
            {"min_active_same_sector": 1, "support_scalar": 1.05},
        ),
        (
            "same_sector_active_gte_1_scalar_1p10",
            {"min_active_same_sector": 1, "support_scalar": 1.10},
        ),
        (
            "same_sector_active_gte_1_scalar_1p20",
            {"min_active_same_sector": 1, "support_scalar": 1.20},
        ),
        (
            "same_sector_active_gte_1_scalar_1p35",
            {"min_active_same_sector": 1, "support_scalar": 1.35},
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for existing in handle:
                if f'"experiment_id": "{EXPERIMENT_ID}"' in existing:
                    return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
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


def _scale_trade_notional(
    trade: dict[str, Any],
    *,
    scalar: float,
    active_same_sector_count: int,
    applied: bool,
) -> dict[str, Any]:
    out = dict(trade)
    original_notional = float(out.get("notional") or 0.0)
    original_shares = float(out.get("shares") or 0.0)
    original_pnl = float(out.get("pnl") or 0.0)
    effective_scalar = scalar if applied else 1.0
    out["pre_sector_crowding_notional"] = round(original_notional, 2)
    out["pre_sector_crowding_shares"] = round(original_shares, 8)
    out["pre_sector_crowding_pnl"] = round(original_pnl, 2)
    out["sector_open_crowding_rule_version"] = RULE_VERSION
    out["sector_open_crowding_active_same_sector_count"] = active_same_sector_count
    out["sector_open_crowding_support_applied"] = bool(applied)
    out["sector_open_crowding_support_scalar"] = round(effective_scalar, 6)
    out["notional"] = round(original_notional * effective_scalar, 2)
    out["shares"] = round(original_shares * effective_scalar, 8)
    out["pnl"] = round(original_pnl * effective_scalar, 2)
    return out


def _apply_sector_open_crowding_support(
    trades: list[dict[str, Any]],
    *,
    min_active_same_sector: int,
    support_scalar: float,
) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    ordered = sorted(
        trades,
        key=lambda row: (
            str(row.get("entry_date") or ""),
            int(row.get("rank") or 99),
            str(row.get("decision_date") or ""),
            str(row.get("ticker") or ""),
        ),
    )
    for raw in ordered:
        entry_date = str(raw.get("entry_date") or "")
        active = [
            row
            for row in active
            if str(row.get("exit_date") or "") >= entry_date
        ]
        sector = prior._sector_key(raw)
        active_same_sector = (
            sum(1 for row in active if prior._sector_key(row) == sector)
            if sector is not None
            else 0
        )
        applied = bool(
            sector is not None
            and active_same_sector >= int(min_active_same_sector)
            and float(support_scalar) > 1.0
        )
        trade = _scale_trade_notional(
            raw,
            scalar=float(support_scalar),
            active_same_sector_count=active_same_sector,
            applied=applied,
        )
        adjusted.append(trade)
        active.append(trade)
    return adjusted


def _sector_counts(trades: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trade in trades:
        sector = prior._sector_key(trade) or "Unknown"
        counts[sector] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _sector_pnl(trades: list[dict[str, Any]]) -> dict[str, float]:
    pnl: dict[str, float] = defaultdict(float)
    for trade in trades:
        sector = prior._sector_key(trade) or "Unknown"
        pnl[sector] += float(trade.get("pnl") or 0.0)
    return {
        sector: round(value, 2)
        for sector, value in sorted(pnl.items(), key=lambda item: (-item[1], item[0]))
    }


def _trade_rows(trades: list[dict[str, Any]], *, limit: int = 40) -> list[dict[str, Any]]:
    rows = []
    for trade in sorted(trades, key=lambda row: (row["entry_date"], row["ticker"]))[:limit]:
        rows.append(
            {
                "ticker": trade["ticker"],
                "window": trade.get("window"),
                "sector": trade.get("sector"),
                "decision_date": trade["decision_date"],
                "entry_date": trade["entry_date"],
                "exit_date": trade["exit_date"],
                "rank": trade.get("rank"),
                "score": trade.get("score"),
                "notional": trade.get("notional"),
                "pre_sector_crowding_notional": trade.get("pre_sector_crowding_notional"),
                "pnl": trade.get("pnl"),
                "pre_sector_crowding_pnl": trade.get("pre_sector_crowding_pnl"),
                "net_return_pct": trade.get("net_return_pct"),
                "sector_open_crowding_active_same_sector_count": trade.get(
                    "sector_open_crowding_active_same_sector_count"
                ),
                "sector_open_crowding_support_applied": trade.get(
                    "sector_open_crowding_support_applied"
                ),
                "sector_open_crowding_support_scalar": trade.get(
                    "sector_open_crowding_support_scalar"
                ),
                "ret20_excess_spy": trade.get("ret20_excess_spy"),
                "ret60": trade.get("ret60"),
                "ret5": trade.get("ret5"),
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "realized_volatility_20": trade.get("realized_volatility_20"),
            }
        )
    return rows


def _window_sleeve_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    adjusted = [row for row in trades if row.get("sector_open_crowding_support_applied")]
    pre_adjusted_pnl = sum(float(row.get("pre_sector_crowding_pnl") or 0.0) for row in adjusted)
    adjusted_pnl = sum(float(row.get("pnl") or 0.0) for row in adjusted)
    pre_notional = sum(float(row.get("pre_sector_crowding_notional") or 0.0) for row in adjusted)
    post_notional = sum(float(row.get("notional") or 0.0) for row in adjusted)
    wins = sum(1 for row in trades if float(row.get("pnl") or 0.0) > 0)
    return {
        "trade_count": len(trades),
        "pnl": round(sum(float(row.get("pnl") or 0.0) for row in trades), 2),
        "win_rate": round(wins / len(trades), 4) if trades else None,
        "sector_open_crowding_adjusted_trade_count": len(adjusted),
        "sector_open_crowding_pre_adjusted_pnl": round(pre_adjusted_pnl, 2),
        "sector_open_crowding_adjusted_pnl": round(adjusted_pnl, 2),
        "sector_open_crowding_pnl_added": round(adjusted_pnl - pre_adjusted_pnl, 2),
        "sector_open_crowding_notional_added": round(post_notional - pre_notional, 2),
        "sector_counts": _sector_counts(trades),
        "sector_pnl": _sector_pnl(trades),
        "adjusted_sector_counts": _sector_counts(adjusted),
        "sample_trades": _trade_rows(trades, limit=25),
        "adjusted_trades_sample": _trade_rows(adjusted, limit=25),
    }


def _variant_payload(
    *,
    variant_name: str,
    min_active_same_sector: int,
    support_scalar: float,
    control_metrics: dict[str, dict[str, Any]],
    before_metrics: dict[str, dict[str, Any]],
    baseline_trades_by_window: dict[str, list[dict[str, Any]]],
    prices: dict[str, list[dict[str, Any]]],
    baseline_replay_parity_passed: bool,
) -> dict[str, Any]:
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_trades: list[dict[str, Any]] = []
    for label, spec in WINDOWS.items():
        adjusted_trades = _apply_sector_open_crowding_support(
            baseline_trades_by_window[label],
            min_active_same_sector=min_active_same_sector,
            support_scalar=support_scalar,
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
    adjusted = [row for row in all_trades if row.get("sector_open_crowding_support_applied")]
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
        variant_name != "baseline_no_sector_open_crowding_support"
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
        "min_active_same_sector": min_active_same_sector,
        "support_scalar": support_scalar,
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
            sum(float(row.get("pre_sector_crowding_pnl") or 0.0) for row in adjusted),
            2,
        ),
        "notional_added": round(
            sum(
                float(row.get("notional") or 0.0)
                - float(row.get("pre_sector_crowding_notional") or 0.0)
                for row in adjusted
            ),
            2,
        ),
        "single_ticker_positive_share": single_share,
        "top5_positive_share": top5_share,
        "event_risk": p35._event_risk(all_trades),
        "sector_counts": _sector_counts(all_trades),
        "sector_pnl": _sector_pnl(all_trades),
        "adjusted_sector_counts": _sector_counts(adjusted),
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
            "max_drawdown_worse": delta["max_drawdown_worse_max"],
            "max_drawdown_worse_allowed": p35.MAX_DRAWDOWN_WORSE,
            "drawdown_guard_passed": drawdown_guard_passed,
            "baseline_replay_parity_passed": baseline_replay_parity_passed,
        },
    }


def _choose_selected(variants: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [row for row in variants if row["gate4"]["passed"]]
    pool = passing or [row for row in variants if row["variant_name"] != "baseline_no_sector_open_crowding_support"]
    return max(
        pool,
        key=lambda row: (
            bool(row["gate4"]["passed"]),
            float(row["delta_metrics"]["aggregate_ev_delta"]),
            float(row["delta_metrics"]["aggregate_pnl_delta"]),
            -float(row["delta_metrics"]["max_drawdown_worse_max"]),
        ),
    )


def _sweep_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in variants:
        delta = row["delta_metrics"]
        rows.append(
            {
                "variant_name": row["variant_name"],
                "min_active_same_sector": row["min_active_same_sector"],
                "support_scalar": row["support_scalar"],
                "aggregate_ev_delta": delta["aggregate_ev_delta"],
                "aggregate_pnl_delta": delta["aggregate_pnl_delta"],
                "windows_ev_improved": delta["windows_ev_improved"],
                "windows_ev_regressed": delta["windows_ev_regressed"],
                "windows_pnl_regressed": delta["windows_pnl_regressed"],
                "max_drawdown_worse_max": delta["max_drawdown_worse_max"],
                "adjusted_trade_count": row["adjusted_trade_count"],
                "adjusted_windows": row["adjusted_windows"],
                "pre_adjusted_pnl": row["pre_adjusted_pnl"],
                "adjusted_pnl": row["adjusted_pnl"],
                "notional_added": row["notional_added"],
                "selected_trade_count": row["selected_trade_count"],
                "single_ticker_positive_share": row["single_ticker_positive_share"],
                "top5_positive_share": row["top5_positive_share"],
                "event_risk": row["event_risk"],
                "passed": row["gate4"]["passed"],
            }
        )
    return rows


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Sector Open-Crowding Support",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: already-selected broad-market paper trades receive "
            "a paper-notional support scalar when another same-sector broad-market "
            "paper position is still open."
        ),
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
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
                adj=sleeve["sector_open_crowding_adjusted_trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Sweep Summary",
            "",
            "```json",
            json.dumps(_safe(payload["sweep_summary"]), indent=2, sort_keys=True),
            "```",
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
        raise RuntimeError(f"Missing source artifact: {prior._repo_rel(SOURCE_JSON)}")
    if not CONTROL_JSON.exists():
        raise RuntimeError(f"Missing control artifact: {prior._repo_rel(CONTROL_JSON)}")
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
    variants = [
        _variant_payload(
            variant_name=name,
            min_active_same_sector=int(values["min_active_same_sector"]),
            support_scalar=float(values["support_scalar"]),
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            baseline_trades_by_window=baseline["trades_by_window"],
            prices=baseline["prices"],
            baseline_replay_parity_passed=baseline["parity_passed"],
        )
        for name, values in SUPPORT_SWEEP.items()
    ]
    selected = _choose_selected(variants)
    gate4_passed = bool(selected["gate4"]["passed"])
    status = "observed_only" if gate4_passed else "rejected"
    decision = (
        "observed_positive_broad_market_sector_open_crowding_support_requires_shared_adapter"
        if gate4_passed
        else "rejected_broad_market_sector_open_crowding_support"
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
            "If positive, implement through shared broad_market_paper_sleeve "
            "state-aware default-off adapter before retention; this run does "
            "not create production/backtest behavior divergence because it "
            "does not promote the support scalar."
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
            "A broad-market paper candidate whose sector is already open may "
            "be joining confirmed sector momentum rather than redundant hidden "
            "beta. A bounded paper-notional support scalar on same-sector open "
            "crowding should improve replacement value without changing "
            "candidate discovery."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / risk allocation",
            "playbook_alignment": (
                "Uses the playbook's broad-market candidate-pool and free "
                "data-edge direction. It consumes the accepted sector map "
                "from exp-20260525-038 and the rejected exp-20260527-901 "
                "sign-check evidence, while avoiding VCP/VBB/state-surface/"
                "LLM/Companyfacts threshold retries."
            ),
            "why_now": (
                "exp-20260527-901 rejected same-sector crowding haircuts and "
                "showed the adjusted same-sector cohort had positive PnL in "
                "all three windows, so this run tests the opposite sign as a "
                "pre-registered single variable."
            ),
        },
        "history_check": {
            "nearby_experiments": [
                "exp-20260520-004 accepted broad-market trend-persistence notional support",
                "exp-20260525-038 accepted broad-market sector map attribution",
                "exp-20260527-901 rejected broad-market same-sector open-crowding haircut",
            ],
            "anti_repeat": (
                "Keeps the accepted broad-market candidate set, rank profile, "
                "low-extension support, high-volatility support, trend-"
                "persistence support, hold days, entry slots, and universe "
                "fixed. Only same-sector open-position support scalar changes."
            ),
            "past_similar_experiment_result": (
                "exp-20260527-901 haircut variants failed because same-sector "
                "open-crowding cohorts were net positive; best 0.80x variant "
                "cut aggregate PnL by $1,299.98 and regressed PnL in all windows."
            ),
        },
        "change_type": "default_off_paper_capital_allocation_scout",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": "broad_market_sector_open_crowding_paper_allocation",
        "trial_variant_id": "same_sector_open_support_v1",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260520-004",
            "exp-20260525-038",
            "exp-20260527-901",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "rejected_haircut_sign_check_plus_production_visible_sector_open_state",
        "changed_variable": "broad_market_sector_open_crowding_support_scalar",
        "single_causal_variable": (
            "paper-notional support for already-selected broad-market trades "
            "when same-sector sleeve exposure is open"
        ),
        "component": "quant/experiments/exp_20260527_021_broad_market_sector_open_crowding_support.py",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "sector_map_experiment_id": SECTOR_MAP_EXPERIMENT_ID,
            "prior_crowding_experiment_id": PRIOR_CROWDING_EXPERIMENT_ID,
            "rule_version": RULE_VERSION,
            "sweep": SUPPORT_SWEEP,
            "selected_variant": selected["variant_name"],
            "selected_min_active_same_sector": selected["min_active_same_sector"],
            "selected_support_scalar": selected["support_scalar"],
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
            "replays the identical selected broad-market paper trades with one "
            "sector open-crowding paper-notional support variable."
        ),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": SOURCE_EXPERIMENT_ID,
            "baseline_artifact": prior._repo_rel(SOURCE_JSON),
            "control_artifact": prior._repo_rel(CONTROL_JSON),
            "standard_protocol": "docs/backtesting.md canonical three fixed windows",
            "before_aggregate": aggregate_before,
            "baseline_replay_parity": baseline_replay_parity,
            "known_measurement_boundary": (
                "Historical replay uses the frozen exp-20260520-004 candidate "
                "universe and sector cache. The tested support is not promoted "
                "into production/default-off paper behavior in this commit."
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
            "min_active_same_sector": selected["min_active_same_sector"],
            "support_scalar": selected["support_scalar"],
            "selected_trade_count": selected["selected_trade_count"],
            "adjusted_trade_count": selected["adjusted_trade_count"],
            "adjusted_windows": selected["adjusted_windows"],
            "pre_adjusted_pnl": selected["pre_adjusted_pnl"],
            "adjusted_pnl": selected["adjusted_pnl"],
            "notional_added": selected["notional_added"],
            "selected_ticker_count": selected["selected_ticker_count"],
            "single_ticker_positive_share": selected["single_ticker_positive_share"],
            "top5_positive_share": selected["top5_positive_share"],
            "event_risk": selected["event_risk"],
            "sector_counts": selected["sector_counts"],
            "sector_pnl": selected["sector_pnl"],
            "adjusted_sector_counts": selected["adjusted_sector_counts"],
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
                "capital/risk allocation: same-sector open broad-market paper "
                "exposure may confirm sector momentum and should receive a "
                "bounded paper-notional support scalar."
            ),
            "2_past_similar_experiments": (
                "exp-20260527-901 tested the opposite haircut sign and failed; "
                "the same-sector adjusted cohort was net positive across all "
                "three windows, so this is a sign-correction scout, not a "
                "candidate-threshold retune."
            ),
            "3_single_variable": (
                "Only same-sector open crowding support scalar changes; "
                "candidate eligibility, ranking, existing support scalars, "
                "hold, slots, and universe remain fixed."
            ),
            "4_acceptance": (
                "Gate 4 requires positive aggregate EV/PnL, all 3 windows EV-"
                "positive, no EV/PnL regression windows, >=8 adjusted trades "
                "across all 3 windows, concentration guard, <=0.5pp drawdown "
                "worsening, and baseline replay parity."
            ),
            "5_reproducibility": (
                "Script, JSON artifact, ticket, markdown artifact, and docs "
                "JSONL record windows, source artifact, sweep parameters, "
                "Gate 1-4, and selected result."
            ),
        },
        "interpretation": (
            "Sector open-crowding support is tested as a capital allocation "
            "layer on the accepted broad-market paper sleeve. Because the "
            "current run does not promote a shared state-aware adapter, "
            "positive evidence is only an observed lead and cannot affect production."
        ),
        "rejection_reason": None if gate4_passed else "Best sector open-crowding support variant failed Gate 4.",
        "next_evidence_needed": (
            "If rejected, do not retry adjacent same-sector support scalars "
            "without new forward closed outcomes. Next broad-market data edge "
            "should use a distinct field such as industry-level leadership "
            "breadth or cost-adjusted replacement value."
            if not gate4_passed
            else "Implement a shared state-aware default-off broad-market "
            "paper adapter plus parity tests before retaining this positive "
            "capital-allocation rule."
        ),
        "why_not_other_changes": [
            "No VCP/VBB threshold or rank-profile retune.",
            "No state-surface notional scalar retune.",
            "No LLM soft-ranking or prompt change.",
            "No Companyfacts+RS growth/RS/top-N/cooldown/extension retry.",
            "No broad-market candidate universe expansion or noise ticker add.",
            "No core/live production order path change.",
        ],
        "known_risks": [
            "Same-day same-sector entries are counted in rank order as ex-ante batch crowding.",
            "The sector cache is a yfinance proxy and unresolved tickers are not adjusted.",
            "A positive replay would still need shared stateful production parity before retention.",
        ],
        "related_files": {
            "script": prior._repo_rel(Path(__file__)),
            "output": prior._repo_rel(OUT_JSON),
            "log": prior._repo_rel(LOG_JSON),
            "ticket": prior._repo_rel(TICKET_JSON),
            "doc_ticket": prior._repo_rel(DOC_TICKET_JSON),
            "artifact": prior._repo_rel(ARTIFACT_MD),
            "experiment_log": prior._repo_rel(EXPERIMENT_LOG),
            "source": prior._repo_rel(SOURCE_JSON),
            "control": prior._repo_rel(CONTROL_JSON),
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
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
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
        "anti_js": "No JavaScript was used.",
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
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
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
