"""exp-20260525-002 low-deployment ETF small-cap breadth confirmation.

Alpha search, replay-only. The accepted low-deployment ETF overlay chooses the
highest raw prior 20-day momentum ETF when the core book has <= 1 active A/B
position. This experiment changes one production-visible market-internal
variable only:

    require IWM prior 20-day momentum, relative to SPY prior 20-day momentum,
    to clear a swept minimum spread before the accepted ETF overlay can fire.

The ETF pool, activation threshold, raw momentum selector, notional, core
strategy, LLM/news replay, and live/default order path remain unchanged. This
tests whether idle-capital replacement value is better when market breadth is
not only cap-weight leadership.
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
import exp_20260522_004_low_deployment_etf_volatility_cap as helper  # noqa: E402


EXPERIMENT_ID = "exp-20260525-002"
STEM = "low_deployment_etf_smallcap_breadth_confirmation"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "accepted_raw_momentum_v1"
SMALLCAP_BREADTH_VARIANTS: "OrderedDict[str, float]" = OrderedDict(
    [
        ("iwm_lag_max_500bp", -0.0500),
        ("iwm_lag_max_250bp", -0.0250),
        ("iwm_lag_max_100bp", -0.0100),
        ("iwm_not_lagging", 0.0000),
        ("iwm_leads_100bp", 0.0100),
        ("iwm_leads_250bp", 0.0250),
    ]
)

WINDOWS = helper.WINDOWS
INITIAL_CAPITAL = helper.INITIAL_CAPITAL
MAX_ACTIVE_CORE_POSITIONS = helper.MAX_ACTIVE_CORE_POSITIONS
OVERLAY_CANDIDATES = helper.OVERLAY_CANDIDATES
OVERLAY_NOTIONAL_FRACTION = helper.OVERLAY_NOTIONAL_FRACTION
STATE_MOMENTUM_DAYS = helper.STATE_MOMENTUM_DAYS
STATE_SMA_DAYS = helper.STATE_SMA_DAYS


def _round(value: Any, digits: int = 4) -> Any:
    return helper._round(value, digits)


def _safe(value: Any) -> Any:
    return helper._safe(value)


def _repo_rel(path: Path | str) -> str:
    return helper._repo_rel(path)


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


def _momentum20(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < STATE_MOMENTUM_DAYS + 1:
        return None
    prior_idx = idx - 1
    previous = float(rows[prior_idx - STATE_MOMENTUM_DAYS]["close"])
    if previous <= 0:
        return None
    return float(rows[prior_idx]["close"]) / previous - 1.0


def _smallcap_breadth_state(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    index_by_ticker_date: dict[str, dict[str, int]],
    day: str,
    *,
    min_iwm_spy_momentum_spread: float | None,
) -> dict[str, Any] | None:
    if min_iwm_spy_momentum_spread is None:
        return {
            "breadth_gate_enabled": False,
            "iwm_momentum20": None,
            "spy_momentum20": None,
            "iwm_spy_momentum_spread": None,
            "min_iwm_spy_momentum_spread": None,
        }
    spy_idx = index_by_ticker_date.get("SPY", {}).get(day)
    iwm_idx = index_by_ticker_date.get("IWM", {}).get(day)
    if spy_idx is None or iwm_idx is None:
        return None
    spy_momentum = _momentum20(rows_by_ticker.get("SPY", []), spy_idx)
    iwm_momentum = _momentum20(rows_by_ticker.get("IWM", []), iwm_idx)
    if spy_momentum is None or iwm_momentum is None:
        return None
    spread = iwm_momentum - spy_momentum
    if spread < min_iwm_spy_momentum_spread:
        return None
    return {
        "breadth_gate_enabled": True,
        "iwm_momentum20": iwm_momentum,
        "spy_momentum20": spy_momentum,
        "iwm_spy_momentum_spread": spread,
        "min_iwm_spy_momentum_spread": min_iwm_spy_momentum_spread,
    }


def _candidate_state(rows: list[dict[str, Any]], idx: int) -> dict[str, Any] | None:
    if idx < max(STATE_SMA_DAYS, STATE_MOMENTUM_DAYS) + 1:
        return None
    prior_idx = idx - 1
    prior = rows[prior_idx]
    sma_window = rows[prior_idx - STATE_SMA_DAYS + 1 : prior_idx + 1]
    sma = sum(float(item["close"]) for item in sma_window) / len(sma_window)
    momentum = float(prior["close"]) / float(rows[prior_idx - STATE_MOMENTUM_DAYS]["close"]) - 1.0
    if float(prior["close"]) <= sma or momentum <= 0.0:
        return None
    return {
        "prior_close": float(prior["close"]),
        "prior_sma200": sma,
        "prior_momentum20": momentum,
    }


def _select_overlay_ticker(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    index_by_ticker_date: dict[str, dict[str, int]],
    day: str,
    *,
    min_iwm_spy_momentum_spread: float | None,
) -> dict[str, Any] | None:
    breadth_state = _smallcap_breadth_state(
        rows_by_ticker,
        index_by_ticker_date,
        day,
        min_iwm_spy_momentum_spread=min_iwm_spy_momentum_spread,
    )
    if breadth_state is None:
        return None

    candidates = []
    for ticker, rows in rows_by_ticker.items():
        idx = index_by_ticker_date.get(ticker, {}).get(day)
        if idx is None:
            continue
        state = _candidate_state(rows, idx)
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
    selected = max(candidates, key=lambda row: (row["momentum"], row["ticker"]))
    selected["breadth_state"] = breadth_state
    return selected


def _overlay_path(
    result: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    variant: str,
    min_iwm_spy_momentum_spread: float | None,
) -> dict[str, Any]:
    base_curve = result.get("equity_curve") or []
    core_counts = helper._core_active_count_by_date(result)
    index_by_ticker_date = {
        ticker: helper._rows_by_date(rows) for ticker, rows in rows_by_ticker.items()
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
            min_iwm_spy_momentum_spread=min_iwm_spy_momentum_spread,
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
        breadth = selection["breadth_state"]
        overlay_days.append(
            {
                "date": day,
                "ticker": ticker,
                "active_core_positions": active_count,
                "prior_close": _round(state["prior_close"], 4),
                "prior_sma200": _round(state["prior_sma200"], 4),
                "prior_momentum20": _round(state["prior_momentum20"], 6),
                "iwm_momentum20": _round(breadth["iwm_momentum20"], 6),
                "spy_momentum20": _round(breadth["spy_momentum20"], 6),
                "iwm_spy_momentum_spread": _round(
                    breadth["iwm_spy_momentum_spread"], 6
                ),
                "min_iwm_spy_momentum_spread": min_iwm_spy_momentum_spread,
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
    min_iwm_spy_momentum_spread: float | None,
) -> dict[str, Any]:
    overlay = _overlay_path(
        result,
        helper._load_snapshot_rows(window["snapshot"]),
        variant=variant,
        min_iwm_spy_momentum_spread=min_iwm_spy_momentum_spread,
    )
    before = helper._metrics(result)
    after = helper._metrics_with_overlay(result, overlay)
    return {
        "before": before,
        "after": after,
        "delta": helper._delta(after, before),
        "overlay_total_pnl": overlay["overlay_total_pnl"],
        "overlay_day_count": overlay["overlay_day_count"],
        "low_deployment_day_count": overlay["low_deployment_day_count"],
        "ticker_day_counts": overlay["ticker_day_counts"],
        "overlay_days": overlay["overlay_days"],
        "overlay_days_sample": overlay["overlay_days"][:20],
    }


def _gate4(
    variant_delta: dict[str, Any],
    candidate_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    aggregate = variant_delta["aggregate"]
    concentration = helper._single_ticker_positive_share(
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
            "Three canonical backtesting.md windows, small-cap breadth variants "
            "measured against accepted raw-momentum v1 low-deployment ETF overlay."
        ),
        "rule": (
            "Require 3/3 EV improvement versus v1, no EV/PnL regression, positive "
            "aggregate EV/PnL, max drawdown worsening <= 1pp, single ETF positive "
            "contribution share <= 75%, at least 4 overlay days in each window, "
            "and at least 2% aggregate EV or PnL uplift versus accepted v1."
        ),
    }


def _best_variant(variant_payloads: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
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
        f"# {EXPERIMENT_ID} Low-deployment ETF Small-cap Breadth Confirmation",
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
        "| Variant | IWM-SPY min spread | EV delta | PnL delta | EV windows +/- | PnL windows +/- | DD max delta | Overlay days | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for variant, row in payload["variant_results"].items():
        agg = row["delta_metrics"]["aggregate"]
        lines.append(
            "| {variant} | {spread:+.4f} | {ev:+.4f} | ${pnl:+,.2f} | {ev_imp}/{ev_reg} | {pnl_imp}/{pnl_reg} | {dd:+.4f} | {days} | {gate} |".format(
                variant=variant,
                spread=row["min_iwm_spy_momentum_spread"],
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
        "total_pnl_delta": payload["total_pnl_delta"],
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
                min_iwm_spy_momentum_spread=None,
            ),
        )
        for label in WINDOWS
    )

    variant_results: dict[str, dict[str, Any]] = OrderedDict()
    for variant, spread in SMALLCAP_BREADTH_VARIANTS.items():
        after_windows = OrderedDict(
            (
                label,
                _window_row(
                    baseline_results[label],
                    WINDOWS[label],
                    variant=variant,
                    min_iwm_spy_momentum_spread=spread,
                ),
            )
            for label in WINDOWS
        )
        delta_metrics = helper._variant_delta_vs_baseline(after_windows, baseline_windows)
        variant_results[variant] = {
            "min_iwm_spy_momentum_spread": spread,
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
        decision = "accepted_default_off_low_deployment_etf_smallcap_breadth_confirmation"
        rejection_reason = None
        decision_rationale = (
            "The small-cap breadth confirmation beat the accepted raw-momentum v1 "
            "overlay across all three canonical windows and cleared materiality, "
            "drawdown, sample, and concentration guards. Promotion would still "
            "require moving the field into the shared default-off paper module "
            "and adding parity tests before any live/default behavior changes."
        )
    else:
        decision = "rejected_low_deployment_etf_smallcap_breadth_confirmation"
        rejection_reason = (
            "No IWM-minus-SPY breadth confirmation variant beat the accepted "
            "raw-momentum v1 overlay across the three-window EV/PnL/drawdown/"
            "concentration gate."
        )
        decision_rationale = rejection_reason

    before_metrics = {label: row["after"] for label, row in baseline_windows.items()}
    after_metrics = best_payload["after_metrics"]

    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "low_deployment_dynamic_etf_overlay_allocation",
        "hypothesis": (
            "On idle-capital days, the accepted low-deployment ETF overlay may "
            "perform better when cap-weight momentum is confirmed by small-cap "
            "breadth. Requiring IWM prior-20d momentum to avoid lagging SPY by "
            "more than a fixed spread could improve replacement value without "
            "changing the ETF pool, notional, or core stock slot logic."
        ),
        "change_type": "alpha_search_overlay_market_internal_confirmation",
        "changed_variable": "low_deployment_etf_overlay_iwm_minus_spy_prior_momentum20_min",
        "single_causal_variable": (
            "Only the IWM-minus-SPY prior-20d momentum spread required before an "
            "ETF overlay day is swept; raw momentum ranking, ETF pool, activation "
            "threshold, notional, core strategy logic, LLM/news replay, and live/"
            "default order paths stay locked."
        ),
        "trial_accounting": {
            "trial_family": "low_deployment_dynamic_etf_overlay_market_internals",
            "changed_variable": "iwm_minus_spy_prior_momentum20_min",
            "prior_trial_count": 7,
            "nearby_prior_experiments": [
                "exp-20260510-007",
                "exp-20260522-004",
                "exp-20260522-018",
                "exp-20260522-021",
                "exp-20260524-023",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "free_ohlcv_market_internal",
            "new_evidence_detail": (
                "Uses prior-close IWM and SPY OHLCV from the same snapshots as the "
                "backtest. This is production-visible without LLM, paid data, "
                "or ticker-pool expansion."
            ),
        },
        "parameters": {
            "baseline_variant": BASELINE_VARIANT,
            "smallcap_breadth_variants": dict(SMALLCAP_BREADTH_VARIANTS),
            "spread_definition": "IWM prior 20d momentum minus SPY prior 20d momentum",
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
                "capital_allocation/ranking: a free OHLCV market-internal breadth "
                "confirmation may improve ETF overlay replacement value during low "
                "core deployment."
            ),
            "2_history_check": {
                "exp-20260510-007": "Accepted raw-momentum dynamic ETF overlay at <=1 active core position.",
                "exp-20260522-004": "Volatility cap rejected; this changes cross-index breadth, not ETF volatility.",
                "exp-20260522-018": "Momentum-lead rejected; this changes market-internal confirmation, not candidate rank spread.",
                "exp-20260522-021": "Active-core scalar rejected; this keeps activation threshold and notional fixed.",
                "exp-20260524-023": "Broad-market crowding replacement was positive but below strict gate; this is a separate low-deployment ETF replay lane.",
            },
            "3_single_variable": "iwm_minus_spy_prior_momentum20_min",
            "4_acceptance_standard": (
                "Compare each breadth variant against accepted raw-momentum v1 over "
                "the three docs/backtesting.md windows; require 3/3 EV improvement, "
                "no EV/PnL regression, positive aggregate EV/PnL, drawdown worsening "
                "<=1pp, concentration <=75%, and >=2% aggregate EV or PnL uplift."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260525_002_low_deployment_etf_smallcap_breadth_confirmation.py"
            ),
        },
        "alpha_hypothesis": {
            "category": "capital_allocation/ranking",
            "playbook_alignment": (
                "Avoids sparse LLM soft-ranking, SEC semantic zero-sample issues, "
                "state-surface scalar retunes, and noisy ticker-pool expansion. It "
                "uses a deterministic free market-internal field in the existing "
                "default-off low-deployment paper lane."
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
                label: helper._metrics(result) for label, result in baseline_results.items()
            },
            "accepted_overlay_baseline_metrics": before_metrics,
        },
        "gate2_field_audit": helper._field_audit(),
        "gate3": {
            "new_core_filter_added": False,
            "new_overlay_candidate_filter_added": True,
            "note": (
                "No core entry filter was added; survival rates are inherited from "
                "the accepted core replay. The only gate is a replay-only ETF "
                "overlay market-internal confirmation measured by actual overlay days."
            ),
            "survival_rates": {
                label: row["before"]["survival_rate"] for label, row in baseline_windows.items()
            },
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "variant_results": variant_results,
        "best_variant": best_name,
        "best_variant_details": {
            "min_iwm_spy_momentum_spread": best_payload[
                "min_iwm_spy_momentum_spread"
            ],
            "delta_metrics": best_payload["delta_metrics"],
            "gate4": best_payload["gate4"],
        },
        "expected_value_score_delta": best_aggregate[
            "candidate_overlay_expected_value_score_delta_sum"
        ],
        "total_pnl_delta": best_aggregate["candidate_overlay_total_pnl_delta_sum"],
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
                "market-internal test does not depend on LLM replay."
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
            "If accepted, implement the breadth gate only in the shared default-off "
            "ETF paper module with focused parity tests; live orders remain disabled. "
            "If rejected, keep raw-momentum v1 and avoid adjacent ETF overlay gates "
            "without forward replacement-value evidence."
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
                    "best_min_iwm_spy_momentum_spread": best_result[
                        "min_iwm_spy_momentum_spread"
                    ],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
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
