"""exp-20260527-901: broad-market sector open-crowding haircut.

Alpha search. Uses the accepted exp-20260520-004 broad-market paper sleeve
and the accepted exp-20260525-038 sector map to test one causal variable:
whether already-selected broad-market paper trades deserve lower paper
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


EXPERIMENT_ID = "exp-20260527-901"
EXPERIMENT_SLUG = "broad_market_sector_open_crowding_haircut"
SOURCE_EXPERIMENT_ID = "exp-20260520-004"
SOURCE_SLUG = "broad_market_trend_persistence_notional"
CONTROL_EXPERIMENT_ID = "exp-20260519-036"
SECTOR_MAP_EXPERIMENT_ID = "exp-20260525-038"
RULE_VERSION = "broad_market_sector_open_crowding_haircut_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260519_035_broad_market_price_floor_candidate_pool_shadow as p35  # noqa: E402
import exp_20260520_004_broad_market_trend_persistence_notional as e004  # noqa: E402


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
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SECTOR_HAIRCUT_SWEEP: OrderedDict[str, dict[str, Any]] = OrderedDict(
    [
        (
            "baseline_no_sector_open_crowding_haircut",
            {"min_active_same_sector": 1, "haircut_scalar": 1.00},
        ),
        (
            "same_sector_active_gte_1_scalar_0p90",
            {"min_active_same_sector": 1, "haircut_scalar": 0.90},
        ),
        (
            "same_sector_active_gte_1_scalar_0p80",
            {"min_active_same_sector": 1, "haircut_scalar": 0.80},
        ),
        (
            "same_sector_active_gte_1_scalar_0p65",
            {"min_active_same_sector": 1, "haircut_scalar": 0.65},
        ),
        (
            "same_sector_active_gte_1_scalar_0p50",
            {"min_active_same_sector": 1, "haircut_scalar": 0.50},
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


def _compact_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        label: {
            key: value
            for key, value in row.items()
            if key != "combined_equity_curve"
        }
        for label, row in metrics.items()
    }


def _sector_key(trade: dict[str, Any]) -> str | None:
    status = str(trade.get("sector_coverage_status") or "")
    sector = trade.get("sector")
    if status != "ok" or not sector:
        return None
    return str(sector)


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
    out["sector_open_crowding_haircut_applied"] = bool(applied)
    out["sector_open_crowding_haircut_scalar"] = round(effective_scalar, 6)
    out["notional"] = round(original_notional * effective_scalar, 2)
    out["shares"] = round(original_shares * effective_scalar, 8)
    out["pnl"] = round(original_pnl * effective_scalar, 2)
    return out


def _apply_sector_open_crowding_haircut(
    trades: list[dict[str, Any]],
    *,
    min_active_same_sector: int,
    haircut_scalar: float,
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
        sector = _sector_key(raw)
        active_same_sector = (
            sum(1 for row in active if _sector_key(row) == sector)
            if sector is not None
            else 0
        )
        applied = bool(
            sector is not None
            and active_same_sector >= int(min_active_same_sector)
            and float(haircut_scalar) < 1.0
        )
        trade = _scale_trade_notional(
            raw,
            scalar=float(haircut_scalar),
            active_same_sector_count=active_same_sector,
            applied=applied,
        )
        adjusted.append(trade)
        active.append(trade)
    return adjusted


def _resimulate_source_baseline(source_payload: dict[str, Any]) -> dict[str, Any]:
    frozen_tickers = sorted(
        str(ticker).upper()
        for ticker in (source_payload.get("candidate_universe") or {}).get("tickers") or []
        if ticker
    )
    if not frozen_tickers:
        raise RuntimeError("Source artifact missing candidate_universe.tickers")

    prices = p35._load_price_rows(frozen_tickers)
    indexes = p35._index_by_date(prices)
    selected_name = source_payload["selected_variant"]["variant_name"]
    trend_variant = e004.TREND_PERSISTENCE_SWEEP[selected_name]

    trades_by_window: dict[str, list[dict[str, Any]]] = OrderedDict()
    baseline_pnl_by_window: dict[str, float] = OrderedDict()
    baseline_trade_count_by_window: dict[str, int] = OrderedDict()
    for label in WINDOWS:
        scout = e004._simulate_window(
            label=label,
            positive_day_ratio_20_min=trend_variant["positive_day_ratio_20_min"],
            scalar=trend_variant["scalar"],
            candidate_tickers=frozen_tickers,
            prices=prices,
            indexes=indexes,
        )
        trades = scout["trades"]
        trades_by_window[label] = trades
        baseline_pnl_by_window[label] = round(
            sum(float(row.get("pnl") or 0.0) for row in trades),
            2,
        )
        baseline_trade_count_by_window[label] = len(trades)

    source_pnl_by_window = {
        label: round(
            float(((source_payload.get("broad_market_sleeve") or {}).get(label) or {}).get("pnl") or 0.0),
            2,
        )
        for label in WINDOWS
    }
    source_trade_count_by_window = {
        label: int(
            ((source_payload.get("broad_market_sleeve") or {}).get(label) or {}).get("trade_count") or 0
        )
        for label in WINDOWS
    }
    pnl_drift = {
        label: round(baseline_pnl_by_window[label] - source_pnl_by_window[label], 2)
        for label in WINDOWS
    }
    trade_count_drift = {
        label: baseline_trade_count_by_window[label] - source_trade_count_by_window[label]
        for label in WINDOWS
    }
    parity_passed = all(abs(value) <= 0.01 for value in pnl_drift.values()) and all(
        value == 0 for value in trade_count_drift.values()
    )
    return {
        "candidate_tickers": frozen_tickers,
        "prices": prices,
        "trades_by_window": trades_by_window,
        "baseline_pnl_by_window": baseline_pnl_by_window,
        "source_pnl_by_window": source_pnl_by_window,
        "pnl_drift": pnl_drift,
        "baseline_trade_count_by_window": baseline_trade_count_by_window,
        "source_trade_count_by_window": source_trade_count_by_window,
        "trade_count_drift": trade_count_drift,
        "parity_passed": parity_passed,
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
                "sector_open_crowding_haircut_applied": trade.get(
                    "sector_open_crowding_haircut_applied"
                ),
                "sector_open_crowding_haircut_scalar": trade.get(
                    "sector_open_crowding_haircut_scalar"
                ),
                "ret20_excess_spy": trade.get("ret20_excess_spy"),
                "ret60": trade.get("ret60"),
                "ret5": trade.get("ret5"),
                "positive_day_ratio_20": trade.get("positive_day_ratio_20"),
                "realized_volatility_20": trade.get("realized_volatility_20"),
            }
        )
    return rows


def _sector_counts(trades: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trade in trades:
        sector = _sector_key(trade) or "Unknown"
        counts[sector] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _sector_pnl(trades: list[dict[str, Any]]) -> dict[str, float]:
    pnl: dict[str, float] = defaultdict(float)
    for trade in trades:
        sector = _sector_key(trade) or "Unknown"
        pnl[sector] += float(trade.get("pnl") or 0.0)
    return {
        sector: round(value, 2)
        for sector, value in sorted(pnl.items(), key=lambda item: (-item[1], item[0]))
    }


def _window_sleeve_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    adjusted = [row for row in trades if row.get("sector_open_crowding_haircut_applied")]
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
        "sector_open_crowding_pnl_removed": round(pre_adjusted_pnl - adjusted_pnl, 2),
        "sector_open_crowding_notional_removed": round(pre_notional - post_notional, 2),
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
    haircut_scalar: float,
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
        adjusted_trades = _apply_sector_open_crowding_haircut(
            baseline_trades_by_window[label],
            min_active_same_sector=min_active_same_sector,
            haircut_scalar=haircut_scalar,
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
    adjusted = [row for row in all_trades if row.get("sector_open_crowding_haircut_applied")]
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
        variant_name != "baseline_no_sector_open_crowding_haircut"
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
        "haircut_scalar": haircut_scalar,
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
        "notional_removed": round(
            sum(
                float(row.get("pre_sector_crowding_notional") or 0.0)
                - float(row.get("notional") or 0.0)
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
        if row["variant_name"] != "baseline_no_sector_open_crowding_haircut"
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
            "min_active_same_sector": row["min_active_same_sector"],
            "haircut_scalar": row["haircut_scalar"],
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
            "event_risk": row["event_risk"],
        }
        for row in variants
    ]


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Broad-Market Sector Open-Crowding Haircut",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single causal variable: paper-notional haircut for accepted broad-market",
        "paper entries when the same sector is already active in the sleeve.",
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
                adj=sleeve["sector_open_crowding_adjusted_trade_count"],
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
    baseline = _resimulate_source_baseline(source_payload)
    variants = [
        _variant_payload(
            variant_name=name,
            min_active_same_sector=int(values["min_active_same_sector"]),
            haircut_scalar=float(values["haircut_scalar"]),
            control_metrics=control_metrics,
            before_metrics=before_metrics,
            baseline_trades_by_window=baseline["trades_by_window"],
            prices=baseline["prices"],
            baseline_replay_parity_passed=baseline["parity_passed"],
        )
        for name, values in SECTOR_HAIRCUT_SWEEP.items()
    ]
    selected = _choose_selected(variants)
    gate4_passed = bool(selected["gate4"]["passed"])
    status = "observed_only" if gate4_passed else "rejected"
    decision = (
        "observed_positive_broad_market_sector_open_crowding_haircut_requires_shared_adapter"
        if gate4_passed
        else "rejected_broad_market_sector_open_crowding_haircut"
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
            "does not promote the haircut."
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
            "be partly redundant hidden-beta exposure. A bounded paper-notional "
            "haircut on same-sector open crowding should improve risk-adjusted "
            "replacement value without changing candidate discovery."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / risk allocation",
            "playbook_alignment": (
                "Uses the current playbook's broad-market candidate-pool and "
                "free data-edge direction. It consumes the accepted sector map "
                "from exp-20260525-038 and avoids VCP/VBB/state-surface/LLM "
                "threshold retries."
            ),
            "why_now": (
                "exp-20260525-038 explicitly unblocked broad-market sector "
                "concentration/crowding alpha_search with sector-map parity."
            ),
        },
        "history_check": {
            "nearby_experiments": [
                "exp-20260520-004 accepted broad-market trend-persistence notional support",
                "exp-20260525-038 accepted broad-market sector map attribution",
                "exp-20260526-015 rejected sector breadth breakout",
                "exp-20260526-017 rejected VBB IWM participation confirmation",
            ],
            "anti_repeat": (
                "Keeps the accepted broad-market candidate set, rank profile, "
                "low-extension support, high-volatility support, trend-"
                "persistence support, hold days, entry slots, and universe "
                "fixed. Only same-sector open-position haircut changes."
            ),
            "past_similar_experiment_result": (
                "No recorded alpha_search after exp-20260525-038 tested "
                "same-sector open-position crowding on the accepted broad-"
                "market paper sleeve."
            ),
        },
        "change_type": "default_off_paper_capital_allocation_scout",
        "changed_variable": "broad_market_sector_open_crowding_haircut_scalar",
        "single_causal_variable": (
            "paper-notional haircut for already-selected broad-market trades "
            "when same-sector sleeve exposure is open"
        ),
        "component": "quant/experiments/exp_20260527_901_broad_market_sector_open_crowding_haircut.py",
        "parameters": {
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "control_experiment_id": CONTROL_EXPERIMENT_ID,
            "sector_map_experiment_id": SECTOR_MAP_EXPERIMENT_ID,
            "rule_version": RULE_VERSION,
            "sweep": SECTOR_HAIRCUT_SWEEP,
            "selected_variant": selected["variant_name"],
            "selected_min_active_same_sector": selected["min_active_same_sector"],
            "selected_haircut_scalar": selected["haircut_scalar"],
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
            "sector open-crowding paper-notional haircut variable."
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
                "universe and sector cache. The tested haircut is not promoted "
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
            "haircut_scalar": selected["haircut_scalar"],
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
                "exposure may be redundant hidden beta and should receive a "
                "bounded paper-notional haircut."
            ),
            "2_past_similar_experiments": (
                "exp-20260525-038 only built sector attribution; no subsequent "
                "recorded experiment tested same-sector open-position crowding "
                "on exp-20260520-004."
            ),
            "3_single_variable": (
                "Only same-sector open crowding haircut scalar changes; "
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
            "Sector open-crowding is tested as a capital allocation layer on "
            "the accepted broad-market paper sleeve. Because the current run "
            "does not promote a shared state-aware adapter, positive evidence "
            "is only an observed lead and cannot affect production."
        ),
        "rejection_reason": None if gate4_passed else "Best sector open-crowding haircut variant failed Gate 4.",
        "next_evidence_needed": (
            "If rejected, do not retry adjacent same-sector haircut scalars "
            "without new forward closed outcomes. Next broad-market data edge "
            "should use a distinct field such as sector replacement value by "
            "closed outcomes or industry-level leadership breadth."
            if not gate4_passed
            else "Implement a shared state-aware default-off broad-market "
            "paper adapter plus parity tests before retaining this positive "
            "capital-allocation rule."
        ),
        "why_not_other_changes": [
            "No VCP/VBB threshold or rank-profile retune.",
            "No state-surface notional scalar retune.",
            "No LLM soft-ranking or prompt change.",
            "No broad-market candidate universe expansion or noise ticker add.",
            "No core/live production order path change.",
        ],
        "known_risks": [
            "Same-day same-sector entries are counted in rank order as ex-ante batch crowding.",
            "The sector cache is a yfinance proxy and unresolved tickers are not adjusted.",
            "A positive replay would still need shared stateful production parity before retention.",
        ],
        "related_files": {
            "script": _repo_rel(Path(__file__)),
            "output": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
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
