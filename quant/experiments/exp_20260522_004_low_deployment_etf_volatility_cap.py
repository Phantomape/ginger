"""exp-20260522-004 low-deployment ETF volatility-cap scout.

Alpha search, replay-only. The accepted low-deployment ETF overlay chooses the
highest raw prior 20-day momentum ETF when the core book has <= 1 active A/B
position. This experiment changes one candidate-quality variable only:

    require the selected ETF candidate's prior 20-day realized volatility to be
    below a swept cap, while leaving the ETF pool, activation threshold, raw
    momentum selector, notional, core strategy, LLM/news replay, and live order
    path unchanged.

The aim is to test whether idle-capital replacement value improves by avoiding
high-volatility ETF acceleration days. This is deliberately not promoted into
shared policy unless the three-window gate clears.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from exp_20260510_007_low_deployment_dynamic_etf_overlay import (  # noqa: E402
    INITIAL_CAPITAL,
    MAX_ACTIVE_CORE_POSITIONS,
    OVERLAY_CANDIDATES,
    OVERLAY_NOTIONAL_FRACTION,
    STATE_MOMENTUM_DAYS,
    STATE_SMA_DAYS,
    _core_active_count_by_date,
    _delta,
    _field_audit,
    _load_snapshot_rows,
    _metrics,
    _metrics_with_overlay,
    _repo_rel,
    _rows_by_date,
    _safe,
    _single_ticker_positive_share,
)


EXPERIMENT_ID = "exp-20260522-004"
STEM = "low_deployment_etf_volatility_cap"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "accepted_raw_momentum_v1"
VOL_CAP_VARIANTS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("vol_cap_125bp", 0.0125),
        ("vol_cap_150bp", 0.0150),
        ("vol_cap_200bp", 0.0200),
        ("vol_cap_250bp", 0.0250),
        ("vol_cap_300bp", 0.0300),
        ("vol_cap_400bp", 0.0400),
    ]
)

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = (
        path.read_text(encoding="utf-8", errors="replace").splitlines()
        if path.exists()
        else []
    )
    kept = [line for line in lines if compact not in line and pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _prior_realized_volatility(rows: list[dict[str, Any]], prior_idx: int) -> float | None:
    if prior_idx - STATE_MOMENTUM_DAYS < 0:
        return None
    returns = []
    for idx in range(prior_idx - STATE_MOMENTUM_DAYS + 1, prior_idx + 1):
        previous = float(rows[idx - 1]["close"])
        current = float(rows[idx]["close"])
        if previous <= 0:
            return None
        returns.append(current / previous - 1.0)
    if len(returns) < 2:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((item - mean_return) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def _candidate_state(
    rows: list[dict[str, Any]],
    idx: int,
    *,
    volatility_cap: float | None,
) -> dict[str, Any] | None:
    if idx < max(STATE_SMA_DAYS, STATE_MOMENTUM_DAYS) + 1:
        return None
    prior_idx = idx - 1
    prior = rows[prior_idx]
    sma_window = rows[prior_idx - STATE_SMA_DAYS + 1 : prior_idx + 1]
    sma = sum(float(item["close"]) for item in sma_window) / len(sma_window)
    momentum = float(prior["close"]) / float(rows[prior_idx - STATE_MOMENTUM_DAYS]["close"]) - 1.0
    if float(prior["close"]) <= sma or momentum <= 0.0:
        return None
    realized_volatility = _prior_realized_volatility(rows, prior_idx)
    if volatility_cap is not None:
        if realized_volatility is None or realized_volatility > volatility_cap:
            return None
    return {
        "prior_close": float(prior["close"]),
        "prior_sma200": sma,
        "prior_momentum20": momentum,
        "prior_realized_volatility20": realized_volatility,
        "volatility_cap": volatility_cap,
    }


def _select_overlay_ticker(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    index_by_ticker_date: dict[str, dict[str, int]],
    day: str,
    *,
    volatility_cap: float | None,
) -> dict[str, Any] | None:
    candidates = []
    for ticker, rows in rows_by_ticker.items():
        idx = index_by_ticker_date.get(ticker, {}).get(day)
        if idx is None:
            continue
        state = _candidate_state(rows, idx, volatility_cap=volatility_cap)
        if state is None:
            continue
        candidates.append(
            {
                "ticker": ticker,
                "idx": idx,
                "momentum": float(state["prior_momentum20"]),
                "state": state,
            }
        )
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["momentum"], row["ticker"]))


def _overlay_path(
    result: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    variant: str,
    volatility_cap: float | None,
) -> dict[str, Any]:
    base_curve = result.get("equity_curve") or []
    core_counts = _core_active_count_by_date(result)
    index_by_ticker_date = {
        ticker: _rows_by_date(rows) for ticker, rows in rows_by_ticker.items()
    }
    overlay_pnl_by_date: dict[str, float] = {}
    overlay_days: list[dict[str, Any]] = []
    candidate_counts: Counter[str] = Counter()
    low_deployment_day_count = 0

    for day, _ in base_curve:
        day = str(day)
        active_count = core_counts.get(day, 0)
        if active_count > MAX_ACTIVE_CORE_POSITIONS:
            continue
        low_deployment_day_count += 1
        selection = _select_overlay_ticker(
            rows_by_ticker,
            index_by_ticker_date,
            day,
            volatility_cap=volatility_cap,
        )
        if selection is None:
            continue
        ticker = selection["ticker"]
        rows = rows_by_ticker[ticker]
        row = rows[selection["idx"]]
        notional = INITIAL_CAPITAL * OVERLAY_NOTIONAL_FRACTION
        pnl = notional * (float(row["close"]) / float(row["open"]) - 1.0)
        overlay_pnl_by_date[day] = pnl
        candidate_counts[ticker] += 1
        state = selection["state"]
        overlay_days.append(
            {
                "date": day,
                "ticker": ticker,
                "active_core_positions": active_count,
                "prior_close": _round(state["prior_close"], 4),
                "prior_sma200": _round(state["prior_sma200"], 4),
                "prior_momentum20": _round(state["prior_momentum20"], 6),
                "prior_realized_volatility20": _round(
                    state["prior_realized_volatility20"], 6
                ),
                "volatility_cap": volatility_cap,
                "variant": variant,
                "open": _round(row["open"], 4),
                "close": _round(row["close"], 4),
                "notional": _round(notional, 2),
                "pnl": _round(pnl, 2),
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in base_curve:
        cumulative_overlay += overlay_pnl_by_date.get(str(day), 0.0)
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "combined_equity_curve": combined_curve,
        "overlay_total_pnl": round(sum(overlay_pnl_by_date.values()), 2),
        "overlay_day_count": len(overlay_days),
        "low_deployment_day_count": low_deployment_day_count,
        "ticker_day_counts": dict(candidate_counts),
        "overlay_days": overlay_days,
    }


def _window_row(
    result: dict[str, Any],
    window: dict[str, str],
    *,
    variant: str,
    volatility_cap: float | None,
) -> dict[str, Any]:
    overlay = _overlay_path(
        result,
        _load_snapshot_rows(window["snapshot"]),
        variant=variant,
        volatility_cap=volatility_cap,
    )
    before = _metrics(result)
    after = _metrics_with_overlay(result, overlay)
    return {
        "before": before,
        "after": after,
        "delta": _delta(after, before),
        "overlay_total_pnl": overlay["overlay_total_pnl"],
        "overlay_day_count": overlay["overlay_day_count"],
        "low_deployment_day_count": overlay["low_deployment_day_count"],
        "ticker_day_counts": overlay["ticker_day_counts"],
        "overlay_days": overlay["overlay_days"],
        "overlay_days_sample": overlay["overlay_days"][:20],
    }


def _variant_delta_vs_baseline(
    candidate_windows: dict[str, dict[str, Any]],
    baseline_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict()
    for label, row in candidate_windows.items():
        base = baseline_windows[label]
        by_window[label] = _delta(row["after"], base["after"])
        by_window[label]["overlay_total_pnl"] = round(
            row["overlay_total_pnl"] - base["overlay_total_pnl"],
            2,
        )
        by_window[label]["overlay_day_count"] = (
            row["overlay_day_count"] - base["overlay_day_count"]
        )

    ev_before = sum(row["after"]["expected_value_score"] for row in baseline_windows.values())
    ev_delta = sum(row["expected_value_score"] for row in by_window.values())
    pnl_before = sum(row["after"]["total_pnl"] for row in baseline_windows.values())
    pnl_delta = sum(row["total_pnl"] for row in by_window.values())
    return {
        "by_window": by_window,
        "aggregate": {
            "baseline_overlay_expected_value_score_sum": _round(ev_before, 6),
            "candidate_overlay_expected_value_score_delta_sum": _round(ev_delta, 6),
            "candidate_overlay_expected_value_score_delta_pct": (
                _round(ev_delta / ev_before, 6) if ev_before else None
            ),
            "baseline_overlay_total_pnl_sum": _round(pnl_before, 2),
            "candidate_overlay_total_pnl_delta_sum": _round(pnl_delta, 2),
            "candidate_overlay_total_pnl_delta_pct": (
                _round(pnl_delta / pnl_before, 6) if pnl_before else None
            ),
            "windows_ev_improved": sum(
                1 for row in by_window.values() if row.get("expected_value_score", 0) > 0
            ),
            "windows_ev_regressed": sum(
                1 for row in by_window.values() if row.get("expected_value_score", 0) < 0
            ),
            "windows_pnl_improved": sum(
                1 for row in by_window.values() if row.get("total_pnl", 0) > 0
            ),
            "windows_pnl_regressed": sum(
                1 for row in by_window.values() if row.get("total_pnl", 0) < 0
            ),
            "max_drawdown_delta_max": _round(
                max(row.get("max_drawdown_pct", 0.0) for row in by_window.values()),
                6,
            ),
            "min_overlay_day_count": min(
                row["overlay_day_count"] for row in candidate_windows.values()
            ),
            "overlay_day_count_sum": sum(
                row["overlay_day_count"] for row in candidate_windows.values()
            ),
        },
    }


def _gate4(
    variant_delta: dict[str, Any],
    candidate_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    aggregate = variant_delta["aggregate"]
    concentration = _single_ticker_positive_share(
        {
            label: {"overlay_days": row["overlay_days"]}
            for label, row in candidate_windows.items()
        }
    )
    concentration_ok = concentration is None or concentration <= 0.75
    directional = bool(
        aggregate["windows_ev_improved"] == len(WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and aggregate["candidate_overlay_expected_value_score_delta_sum"] > 0
        and aggregate["candidate_overlay_total_pnl_delta_sum"] > 0
        and aggregate["max_drawdown_delta_max"] <= 0.01
        and aggregate["min_overlay_day_count"] >= 4
        and concentration_ok
    )
    material = bool(
        (aggregate["candidate_overlay_expected_value_score_delta_pct"] or 0.0) >= 0.02
        or (aggregate["candidate_overlay_total_pnl_delta_pct"] or 0.0) >= 0.02
    )
    return {
        "passed": bool(directional and material),
        "passed_directionally": directional,
        "strong_materiality_passed": material,
        "concentration_ok": concentration_ok,
        "single_ticker_positive_share": concentration,
        "basis": (
            "Three canonical backtesting.md windows, volatility-cap variants "
            "measured against accepted raw-momentum v1 low-deployment ETF overlay."
        ),
        "rule": (
            "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive "
            "aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive "
            "contribution share <= 75%, at least 4 overlay days in each window, "
            "and at least 2% aggregate EV or PnL uplift versus accepted v1."
        ),
    }


def _best_variant(
    variant_payloads: dict[str, dict[str, Any]]
) -> tuple[str, dict[str, Any]]:
    passed = [
        (name, payload)
        for name, payload in variant_payloads.items()
        if payload["gate4"]["passed"]
    ]
    pool = passed if passed else list(variant_payloads.items())
    return max(
        pool,
        key=lambda item: item[1]["delta_metrics"]["aggregate"][
            "candidate_overlay_expected_value_score_delta_sum"
        ],
    )


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["best_variant"]
    best_delta = payload["variant_results"][best]["delta_metrics"]
    aggregate = best_delta["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Low-deployment ETF Volatility Cap",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{best}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Variant Sweep",
        "",
        "| Variant | Cap | EV delta | PnL delta | EV windows +/- | PnL windows +/- | DD max delta | Overlay days | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for variant, row in payload["variant_results"].items():
        agg = row["delta_metrics"]["aggregate"]
        lines.append(
            "| {variant} | {cap:.4f} | {ev:+.4f} | ${pnl:+,.2f} | {ev_imp}/{ev_reg} | {pnl_imp}/{pnl_reg} | {dd:+.4f} | {days} | {gate} |".format(
                variant=variant,
                cap=row["volatility_cap"],
                ev=agg["candidate_overlay_expected_value_score_delta_sum"],
                pnl=agg["candidate_overlay_total_pnl_delta_sum"],
                ev_imp=agg["windows_ev_improved"],
                ev_reg=agg["windows_ev_regressed"],
                pnl_imp=agg["windows_pnl_improved"],
                pnl_reg=agg["windows_pnl_regressed"],
                dd=agg["max_drawdown_delta_max"],
                days=agg["overlay_day_count_sum"],
                gate="PASS" if row["gate4"]["passed"] else "FAIL",
            )
        )

    lines.extend(
        [
            "",
            "## Best Variant Three-window Deltas Vs Accepted v1",
            "",
            "| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta | Overlay days delta | Ticker days |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for label, row in best_delta["by_window"].items():
        ticker_counts = ", ".join(
            f"{ticker}:{count}"
            for ticker, count in sorted(
                payload["variant_results"][best]["after_details"][label][
                    "ticker_day_counts"
                ].items()
            )
        )
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {ret:+.4f} | {sharpe:+.2f} | {dd:+.4f} | {days:+d} | {tickers} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                ret=row.get("strategy_total_return_pct", 0.0),
                sharpe=row.get("sharpe_daily", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
                days=int(row.get("overlay_day_count", 0)),
                tickers=ticker_counts or "none",
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta vs v1: `{aggregate['candidate_overlay_expected_value_score_delta_sum']}` (`{aggregate['candidate_overlay_expected_value_score_delta_pct']}`)",
            f"- PnL delta vs v1: `${aggregate['candidate_overlay_total_pnl_delta_sum']}` (`{aggregate['candidate_overlay_total_pnl_delta_pct']}`)",
            f"- EV windows improved/regressed: `{aggregate['windows_ev_improved']}` / `{aggregate['windows_ev_regressed']}`",
            f"- PnL windows improved/regressed: `{aggregate['windows_pnl_improved']}` / `{aggregate['windows_pnl_regressed']}`",
            f"- max DD delta max: `{aggregate['max_drawdown_delta_max']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            f"  default_off_paper_only: {payload['production_impact']['default_off_paper_only']}",
            f"  alters_orders: {payload['production_impact']['alters_orders']}",
            "```",
            "",
            "Live/default orders remain unchanged.",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "best_variant": payload["best_variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "artifact": _repo_rel(ARTIFACT_MD),
    }
    _write_json(TICKET_JSON, ticket)


def _build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    baseline_results = OrderedDict()
    for label, window in WINDOWS.items():
        result = BacktestEngine(
            universe=get_universe(),
            start=window["start"],
            end=window["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
        ).run()
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        baseline_results[label] = result

    baseline_windows = OrderedDict(
        (
            label,
            _window_row(
                baseline_results[label],
                WINDOWS[label],
                variant=BASELINE_VARIANT,
                volatility_cap=None,
            ),
        )
        for label in WINDOWS
    )

    variant_results: dict[str, dict[str, Any]] = OrderedDict()
    for variant, cap in VOL_CAP_VARIANTS.items():
        after_windows = OrderedDict(
            (
                label,
                _window_row(
                    baseline_results[label],
                    WINDOWS[label],
                    variant=variant,
                    volatility_cap=cap,
                ),
            )
            for label in WINDOWS
        )
        delta_metrics = _variant_delta_vs_baseline(after_windows, baseline_windows)
        variant_results[variant] = {
            "volatility_cap": cap,
            "after_metrics": {label: row["after"] for label, row in after_windows.items()},
            "delta_metrics": delta_metrics,
            "gate4": _gate4(delta_metrics, after_windows),
            "after_details": {
                label: {
                    "overlay_total_pnl": row["overlay_total_pnl"],
                    "overlay_day_count": row["overlay_day_count"],
                    "low_deployment_day_count": row["low_deployment_day_count"],
                    "ticker_day_counts": row["ticker_day_counts"],
                    "overlay_days_sample": row["overlay_days_sample"],
                }
                for label, row in after_windows.items()
            },
        }

    best_name, best_payload = _best_variant(variant_results)
    best_aggregate = best_payload["delta_metrics"]["aggregate"]
    gate = best_payload["gate4"]

    accepted = bool(gate["passed"])
    if accepted:
        decision = "accepted_default_off_low_deployment_etf_volatility_cap"
        rejection_reason = None
        decision_rationale = (
            "The volatility-cap variant beat the accepted raw-momentum v1 overlay "
            "across all three canonical windows and cleared materiality, drawdown, "
            "sample, and concentration guards. Because this is high multiple-testing "
            "risk within the ETF overlay family, promotion should require a separate "
            "shared default-off paper policy patch and parity test before any live "
            "or default behavior changes."
        )
    else:
        decision = "rejected_low_deployment_etf_volatility_cap"
        rejection_reason = (
            "No volatility-cap variant beat the accepted raw-momentum v1 overlay "
            "across the three-window EV/PnL/drawdown/concentration gate."
        )
        decision_rationale = rejection_reason

    before_metrics = {label: row["after"] for label, row in baseline_windows.items()}

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "low_deployment_dynamic_etf_overlay_allocation",
        "hypothesis": (
            "On idle-capital days, the accepted low-deployment ETF overlay may be "
            "overpaying for high-volatility acceleration. Filtering overlay ETF "
            "candidates by prior 20-day realized volatility could preserve raw "
            "momentum replacement value while reducing drawdown and tail exposure."
        ),
        "change_type": "alpha_search_overlay_candidate_quality_filter",
        "changed_variable": "low_deployment_etf_overlay_prior_realized_volatility20_cap",
        "single_causal_variable": (
            "Only the ETF overlay candidate eligibility volatility cap is swept; "
            "raw momentum ranking, ETF pool, activation threshold, notional, core "
            "strategy logic, LLM/news replay, and live/default order paths stay locked."
        ),
        "trial_accounting": {
            "trial_family": "low_deployment_dynamic_etf_overlay_candidate_quality",
            "changed_variable": "prior_realized_volatility20_cap",
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260510-007",
                "exp-20260512-777",
                "exp-20260518-003",
                "exp-20260520-016",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "new_production_visible_field",
            "new_evidence_detail": (
                "Uses prior-close OHLCV-derived realized volatility, a field that "
                "can be produced in both run.py and backtester.py without LLM replay."
            ),
        },
        "parameters": {
            "baseline_variant": BASELINE_VARIANT,
            "volatility_cap_variants": dict(VOL_CAP_VARIANTS),
            "max_active_core_positions": MAX_ACTIVE_CORE_POSITIONS,
            "candidate_tickers": list(OVERLAY_CANDIDATES),
            "overlay_notional_fraction": OVERLAY_NOTIONAL_FRACTION,
            "state_sma_days": STATE_SMA_DAYS,
            "state_momentum_days": STATE_MOMENTUM_DAYS,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "position caps",
                "portfolio heat",
                "exits",
                "follow-through add-ons",
                "ETF candidate pool",
                "ETF raw momentum selector",
                "ETF activation threshold",
                "ETF notional",
                "LLM/news replay",
                "live/default orders",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "capital_allocation/ranking: a prior realized-volatility cap may "
                "improve ETF overlay replacement value during low core deployment."
            ),
            "2_history_check": {
                "exp-20260510-007": (
                    "Accepted raw-momentum dynamic ETF overlay at <=1 active core position."
                ),
                "exp-20260512-777": (
                    "ETF candidate-pool variants rejected; this keeps the v1 pool fixed."
                ),
                "exp-20260518-003": (
                    "Activation-threshold variants rejected; this keeps <=1 fixed."
                ),
                "exp-20260520-016": (
                    "Risk-adjusted selector rejected; this keeps raw momentum ranking "
                    "and changes candidate eligibility only."
                ),
            },
            "3_single_variable": "prior_realized_volatility20_cap",
            "4_acceptance_standard": (
                "Compare each cap variant against accepted raw-momentum v1 over the "
                "three docs/backtesting.md windows; require 3/3 EV improvement, "
                "no EV/PnL regression, positive aggregate EV/PnL, drawdown worsening "
                "<=1pp, concentration <=75%, and >=2% aggregate EV or PnL uplift."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260522_004_low_deployment_etf_volatility_cap.py"
            ),
        },
        "alpha_hypothesis": {
            "category": "capital_allocation/ranking",
            "playbook_alignment": (
                "Avoids sparse LLM soft-ranking, broad-market identity drift, SEC "
                "semantic zero-sample issues, and state-surface scalar retunes; "
                "uses a deterministic production-visible OHLCV field in the existing "
                "low-deployment paper overlay lane."
            ),
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three-window protocol",
            "core_baseline_metrics": {
                label: _metrics(result) for label, result in baseline_results.items()
            },
            "accepted_overlay_baseline_metrics": before_metrics,
        },
        "gate2_field_audit": _field_audit(),
        "gate3": {
            "new_core_filter_added": False,
            "new_overlay_candidate_filter_added": True,
            "note": (
                "No core entry filter was added; survival rates are inherited from "
                "the accepted core replay. The only filter is a replay-only ETF "
                "overlay candidate quality cap measured by actual overlay day counts."
            ),
            "survival_rates": {
                label: row["before"]["survival_rate"] for label, row in baseline_windows.items()
            },
        },
        "before_metrics": before_metrics,
        "variant_results": variant_results,
        "best_variant": best_name,
        "best_variant_details": {
            "volatility_cap": best_payload["volatility_cap"],
            "delta_metrics": best_payload["delta_metrics"],
            "gate4": best_payload["gate4"],
        },
        "expected_value_score_delta": best_aggregate[
            "candidate_overlay_expected_value_score_delta_sum"
        ],
        "gate4": gate,
        "before_details": {
            label: {
                "overlay_total_pnl": row["overlay_total_pnl"],
                "overlay_day_count": row["overlay_day_count"],
                "low_deployment_day_count": row["low_deployment_day_count"],
                "ticker_day_counts": row["ticker_day_counts"],
                "overlay_days_sample": row["overlay_days_sample"],
            }
            for label, row in baseline_windows.items()
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains sample-limited; this deterministic "
                "candidate-quality test does not depend on LLM replay."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_orders_changed": False,
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": (
            "If accepted, implement the cap only in the shared default-off ETF "
            "paper module with focused parity tests; live orders remain disabled. "
            "If rejected, keep raw-momentum v1 and do not retry adjacent ETF "
            "selector/cap formulas without new forward replacement-value evidence."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }
    return log_record


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_artifact(payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, payload)
    best = payload["best_variant"]
    best_result = payload["variant_results"][best]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": best,
                    "best_volatility_cap": best_result["volatility_cap"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": best_result["delta_metrics"]["aggregate"][
                        "candidate_overlay_total_pnl_delta_sum"
                    ],
                    "gate4": payload["gate4"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
