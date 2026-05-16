"""exp-20260516-035: FINRA short-crowding risk haircut sweep.

Alpha search on one causal variable: a post-sizing risk multiplier for
already-qualified trend/breakout stock signals whose latest PIT-safe FINRA
days-to-cover value is in the same-day universe top quartile.

This is a replay scout only. A positive result must be promoted through a
shared FINRA adapter plus shared risk/sizing policy before live/default
behavior changes.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260516-035"
EXPERIMENT_SLUG = "finra_short_crowding_risk_haircut"
MULTIPLIER_KEY = "finra_short_crowding_risk_multiplier_applied"
STATE_KEY = "finra_short_crowding_top_quartile_state"
BASELINE_RISK_MULTIPLIER = 1.0
RISK_MULTIPLIER_SWEEP = [0.25, 0.5, 0.75, BASELINE_RISK_MULTIPLIER]
TOP_FRACTION = 0.25
STATE_STRATEGIES = {"trend_long", "breakout_long"}
EXCLUDED_SECTORS = {"ETF", "Commodities"}
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MIN_AFFECTED_SIGNAL_COUNT = 6
MIN_AFFECTED_WINDOW_COUNT = 2
WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_short_interest_shadow_experiment import (  # noqa: E402
    FINRA_SCHEDULE_URL,
    FINRA_SOURCE_URL,
    fetch_finra_rows,
    latest_finra_row,
    parse_date,
    settlement_dates,
)


CURRENT_RISK_MULTIPLIER = BASELINE_RISK_MULTIPLIER
FINRA_ROWS_BY_TICKER: dict[str, list[dict[str, Any]]] = {}
FINRA_FILES: list[dict[str, Any]] = []
FINRA_ROWS: list[dict[str, Any]] = []


def _signal_date(ohlcv_data: Any) -> str | None:
    if ohlcv_data is None or len(ohlcv_data) < 1:
        return None
    try:
        return str(ohlcv_data.index[-1].date())
    except Exception:
        return None


def _make_compute_features_wrapper(
    original: Callable[..., dict[str, Any] | None],
) -> Callable[..., dict[str, Any] | None]:
    def wrapped(
        ticker: str,
        ohlcv_data: Any,
        earnings_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        features = original(ticker, ohlcv_data, earnings_data)
        if features is None:
            return None
        out = dict(features)
        out["finra_short_interest_signal_date"] = _signal_date(ohlcv_data)
        return out

    return wrapped


def _ensure_finra_lookup(tickers: set[str]) -> None:
    global FINRA_ROWS_BY_TICKER, FINRA_FILES, FINRA_ROWS
    if FINRA_ROWS_BY_TICKER or FINRA_FILES:
        return

    start = min(parse_date(spec["start"]) for spec in WINDOWS.values()) - timedelta(
        days=45
    )
    end = max(parse_date(spec["end"]) for spec in WINDOWS.values())
    settlements = settlement_dates(start, end)
    rows, files = fetch_finra_rows({ticker.upper() for ticker in tickers}, settlements)

    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_ticker[str(row.get("ticker") or "").upper()].append(row)
    for ticker_rows in by_ticker.values():
        ticker_rows.sort(key=lambda row: row["publication_date"])

    FINRA_ROWS = rows
    FINRA_FILES = files
    FINRA_ROWS_BY_TICKER = dict(by_ticker)


def _latest_short_row(ticker: str, features: dict[str, Any]) -> dict[str, Any] | None:
    signal_date = features.get("finra_short_interest_signal_date")
    if not signal_date:
        return None
    try:
        candidate_date = parse_date(str(signal_date))
    except ValueError:
        return None
    return latest_finra_row(FINRA_ROWS_BY_TICKER, ticker.upper(), candidate_date)


def _days_to_cover_value(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    value = row.get("days_to_cover")
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _daily_days_to_cover_cutoff(
    features_dict: dict[str, dict[str, Any]],
) -> float | None:
    values: list[float] = []
    for ticker, features in (features_dict or {}).items():
        sector = base.risk_engine.SECTOR_MAP.get(ticker, "Unknown")
        if sector in EXCLUDED_SECTORS:
            continue
        value = _days_to_cover_value(_latest_short_row(ticker, features or {}))
        if value is not None:
            values.append(value)
    if not values:
        return None
    values.sort()
    index = max(0, math.ceil(len(values) * (1.0 - TOP_FRACTION)) - 1)
    return values[index]


def _make_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        cutoff = _daily_days_to_cover_cutoff(features_dict)
        cutoff_for_log = round(cutoff, 6) if cutoff is not None else None
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            features = features_dict.get(ticker) or {}
            row = _latest_short_row(ticker, features)
            days_to_cover = _days_to_cover_value(row)
            sig["finra_short_interest_signal_date"] = features.get(
                "finra_short_interest_signal_date"
            )
            sig["finra_short_interest_publication_date"] = (
                row.get("publication_date") if row else None
            )
            sig["finra_short_interest_settlement_date"] = (
                row.get("settlement_date") if row else None
            )
            sig["finra_days_to_cover"] = (
                round(days_to_cover, 6) if days_to_cover is not None else None
            )
            sig["finra_short_interest_change_pct"] = (
                row.get("short_interest_change_pct") if row else None
            )
            sig["finra_short_crowding_top_quartile_cutoff"] = cutoff_for_log
            sig[STATE_KEY] = (
                sig.get("strategy") in STATE_STRATEGIES
                and sig.get("sector") not in EXCLUDED_SECTORS
                and days_to_cover is not None
                and cutoff is not None
                and days_to_cover >= cutoff
            )
        return enriched

    return wrapped


def _scale_sizing(
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0 or scalar >= 1.0:
        return sizing
    new_shares = max(1, int(math.floor(shares * scalar)))
    if new_shares >= shares:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["finra_short_crowding_baseline_shares"] = shares
    out["finra_short_crowding_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = (
        round((entry * new_shares) / portfolio_value, 4)
        if portfolio_value
        else 0.0
    )
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (
        (net_risk_per_share * new_shares) / portfolio_value
        if portfolio_value
        else 0.0
    )
    out[MULTIPLIER_KEY] = scalar
    return out


def _make_size_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if sig.get(STATE_KEY) and sizing.get("shares_to_buy"):
                adjusted_sizing = _scale_sizing(
                    sizing,
                    CURRENT_RISK_MULTIPLIER,
                    portfolio_value,
                )
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "signal_date": sig.get("finra_short_interest_signal_date"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "days_to_cover": sig.get("finra_days_to_cover"),
                            "top_quartile_cutoff": sig.get(
                                "finra_short_crowding_top_quartile_cutoff"
                            ),
                            "publication_date": sig.get(
                                "finra_short_interest_publication_date"
                            ),
                            "settlement_date": sig.get(
                                "finra_short_interest_settlement_date"
                            ),
                            "short_interest_change_pct": sig.get(
                                "finra_short_interest_change_pct"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "scalar": CURRENT_RISK_MULTIPLIER,
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                            "rs20_entry_state_leader": sig.get(
                                "rs20_entry_state_leader"
                            ),
                            "rs60_top_quintile_state": sig.get(
                                "rs60_top_quintile_state"
                            ),
                            "price_vs_200ma_extension_state": sig.get(
                                "price_vs_200ma_extension_state"
                            ),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _apply_gate4_guards(candidate: dict[str, Any]) -> dict[str, Any]:
    max_drawdown_worse = max(
        float(delta.get("max_drawdown_pct") or 0.0)
        for delta in candidate["delta_metrics"]["by_window"].values()
    )
    affected_windows = [
        label for label, rows in candidate["adjustments"].items() if rows
    ]
    sample_guard_passed = (
        candidate["gate4"]["affected_signal_count"] >= MIN_AFFECTED_SIGNAL_COUNT
        and len(affected_windows) >= MIN_AFFECTED_WINDOW_COUNT
    )
    drawdown_passed = max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    candidate["gate4"]["affected_windows"] = affected_windows
    candidate["gate4"]["minimum_affected_signal_count"] = MIN_AFFECTED_SIGNAL_COUNT
    candidate["gate4"]["minimum_affected_window_count"] = MIN_AFFECTED_WINDOW_COUNT
    candidate["gate4"]["sample_guard_passed"] = sample_guard_passed
    candidate["gate4"]["max_drawdown_worse"] = round(max_drawdown_worse, 6)
    candidate["gate4"]["max_drawdown_worse_guardrail"] = (
        MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    candidate["gate4"]["drawdown_guardrail_passed"] = drawdown_passed
    candidate["passed"] = (
        bool(candidate["passed"])
        and sample_guard_passed
        and drawdown_passed
        and not candidate["is_identity_control"]
    )
    candidate["gate4"]["passed"] = candidate["passed"]
    return candidate


def _run_window_with_multiplier(
    label: str,
    multiplier: float,
) -> dict[str, Any]:
    global CURRENT_RISK_MULTIPLIER
    CURRENT_RISK_MULTIPLIER = multiplier
    return base._run_window(label, variant=True)


def _candidate_payload(
    multiplier: float,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    before_metrics = {label: before_runs[label]["metrics"] for label in base.WINDOWS}
    after_metrics: dict[str, dict[str, Any]] = {}
    adjustments: dict[str, list[dict[str, Any]]] = {}
    changed_trades: dict[str, dict[str, Any]] = {}
    sizing_attribution: dict[str, Any] = {}
    is_identity = math.isclose(multiplier, BASELINE_RISK_MULTIPLIER)

    for label in base.WINDOWS:
        variant = (
            before_runs[label]
            if is_identity
            else _run_window_with_multiplier(label, multiplier)
        )
        after_metrics[label] = variant["metrics"]
        adjustments[label] = variant["adjustments"]
        changed_trades[label] = base._changed_trades(
            before_runs[label]["trades"],
            variant["trades"],
        )
        sizing_attribution[label] = {
            "signal": variant["sizing_rule_signal_attribution"].get(MULTIPLIER_KEY),
            "trade": variant["sizing_rule_trade_attribution"].get(MULTIPLIER_KEY),
        }

    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    affected_count = sum(len(rows) for rows in adjustments.values())
    passed = (
        not is_identity
        and aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and affected_count > 0
    )
    return _apply_gate4_guards(
        {
            "risk_multiplier": multiplier,
            "is_identity_control": is_identity,
            "passed": passed,
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "delta_metrics": {
                "by_window": by_window_delta,
                "aggregate_before": aggregate_before,
                "aggregate_after": aggregate_after,
                "aggregate_delta": aggregate_delta,
            },
            "gate4": {
                "passed": passed,
                "improved_windows": improved,
                "regressed_windows": regressed,
                "affected_signal_count": affected_count,
            },
            "adjustments": adjustments,
            "changed_trades": changed_trades,
            "sizing_attribution": sizing_attribution,
            "expected_value_score_delta": aggregate_delta[
                "expected_value_score_sum"
            ],
            "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        }
    )


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    non_identity = [row for row in candidates if not row["is_identity_control"]]
    passed = [row for row in non_identity if row["passed"]]
    pool = passed if passed else non_identity
    return max(
        pool,
        key=lambda row: (
            float(row["expected_value_score_delta"]),
            float(row["total_pnl_delta"]),
            -float(row["gate4"].get("max_drawdown_worse") or 0.0),
        ),
    )


def _sweep_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in candidates:
        rows.append(
            {
                "risk_multiplier": row["risk_multiplier"],
                "is_identity_control": row["is_identity_control"],
                "passed": row["passed"],
                "expected_value_score_delta": row["expected_value_score_delta"],
                "total_pnl_delta": row["total_pnl_delta"],
                "improved_windows": row["gate4"]["improved_windows"],
                "regressed_windows": row["gate4"]["regressed_windows"],
                "affected_signal_count": row["gate4"]["affected_signal_count"],
                "affected_windows": row["gate4"]["affected_windows"],
                "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
                "sample_guard_passed": row["gate4"]["sample_guard_passed"],
                "drawdown_guardrail_passed": row["gate4"][
                    "drawdown_guardrail_passed"
                ],
            }
        )
    return rows


def _finra_coverage_summary() -> dict[str, Any]:
    ok_files = [row for row in FINRA_FILES if row.get("status_code") == 200]
    return {
        "source_urls": [FINRA_SOURCE_URL, FINRA_SCHEDULE_URL],
        "publication_lag": "FINRA schedule/7th-business-day publication date",
        "finra_files_attempted": len(FINRA_FILES),
        "finra_files_ok": len(ok_files),
        "finra_rows_filtered": len(FINRA_ROWS),
        "tickers_with_rows": len(FINRA_ROWS_BY_TICKER),
        "available_fields": [
            "settlement_date",
            "publication_date",
            "short_interest",
            "short_interest_change_pct",
            "days_to_cover",
            "average_daily_volume",
        ],
        "missing_fields": [
            "short_interest_float",
            "borrow_fee",
            "shares_available",
            "hard_to_borrow",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.2f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                windows=", ".join(row["affected_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                affected=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} FINRA Short-Crowding Risk Haircut",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing risk multiplier for already-qualified trend/breakout stock signals whose latest PIT-safe FINRA days-to-cover value is in the same-day universe top quartile. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected non-control multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. A positive promotion must add a shared FINRA publication-lag adapter plus shared risk/sizing attribution used by both backtester.py and run.py, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_modules() -> None:
    base.WINDOWS = WINDOWS
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_compute_features_wrapper = _make_compute_features_wrapper
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_modules()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    _ensure_finra_lookup(set(base.get_universe()))
    before_runs = {
        label: _run_window_with_multiplier(label, BASELINE_RISK_MULTIPLIER)
        for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(multiplier, before_runs)
        for multiplier in RISK_MULTIPLIER_SWEEP
    ]
    selected = _select_candidate(candidates)

    decision = (
        "accepted_for_shared_policy_implementation"
        if selected["passed"]
        else "rejected_finra_short_crowding_risk_haircut"
    )
    interpretation = (
        "FINRA high days-to-cover crowding cleared the canonical three-window scout as a risk-allocation haircut, but remains replay-only until a shared production/backtest FINRA adapter is implemented."
        if selected["passed"]
        else "FINRA high days-to-cover crowding did not clear the canonical three-window gate as a risk-allocation haircut."
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The prior official FINRA shadow study showed high short-interest "
            "crowding underperformed non-high crowding as a standalone long "
            "context. Instead of treating crowding as a squeeze alpha, test it "
            "as a risk-allocation haircut on the fixed accepted candidate set."
        ),
        "change_type": "risk_allocation_shadow",
        "changed_variable": "finra_short_crowding_risk_multiplier",
        "single_causal_variable": (
            "post-sizing risk multiplier for trend/breakout stock signals with "
            "latest PIT-safe FINRA days-to-cover in the same-day universe top quartile"
        ),
        "parameters": {
            "state_definition": {
                "source": "FINRA official biweekly equity short-interest CSV",
                "pit_join": "latest publication_date <= signal_date",
                "feature": "days_to_cover",
                "cutoff": "same-day universe top quartile",
                "top_fraction": TOP_FRACTION,
                "strategies": sorted(STATE_STRATEGIES),
                "excluded_sectors": sorted(EXCLUDED_SECTORS),
            },
            "baseline_risk_multiplier": BASELINE_RISK_MULTIPLIER,
            "risk_multiplier_sweep": RISK_MULTIPLIER_SWEEP,
            "selected_risk_multiplier": selected["risk_multiplier"],
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "minimum_affected_signal_count": MIN_AFFECTED_SIGNAL_COUNT,
            "minimum_affected_window_count": MIN_AFFECTED_WINDOW_COUNT,
            "locked_variables": [
                "core universe",
                "entry filters",
                "candidate ranking",
                "stop and target logic",
                "all existing sizing multipliers",
                "portfolio heat",
                "slot planning",
                "LLM/news replay",
                "event sleeves",
                "candidate pool",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation on official PIT-safe short-interest crowding; "
                "this follows the playbook preference for fixed candidate-set "
                "allocation and uses a deterministic non-LLM source"
            ),
            "2_history_check": {
                "exp-20260505-024": (
                    "FINRA short-interest shadow coverage was PIT-safe, but high "
                    "short crowding underperformed non-high as a long/squeeze "
                    "signal; this tests the opposite use as a risk haircut."
                ),
                "exp-20260516-032": (
                    "Candidate-pool expansion produced old-window regression; "
                    "this keeps the accepted core candidate set fixed."
                ),
                "exp-20260516-033": (
                    "SEC neutral-language notional was rejected and field-limited; "
                    "this avoids LLM/SEC semantic sparsity."
                ),
                "recent_atr_and_space_branches": (
                    "ATR expansion, Space, source-tilt, and SEC scalar variants "
                    "have nearby rejected runs, so this uses an orthogonal data family."
                ),
            },
            "3_single_causal_variable": (
                "finra_short_crowding_risk_multiplier with fixed PIT top-quartile state"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, "
                "at least two EV-improved windows, no EV-regressed windows, survival >= 5%, "
                "at least six affected signals across at least two windows, and max drawdown "
                "drift <= 0.5 pp."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260516_035_finra_short_crowding_risk_haircut.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "finra_data_coverage": _finra_coverage_summary(),
        "gate1": {
            "baseline_metrics": selected["before_metrics"],
            "baseline_aggregate": selected["delta_metrics"]["aggregate_before"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "feature_layer signal date",
                "FINRA publication_date",
                "FINRA days_to_cover",
                "risk_engine sector",
                "risk_engine strategy",
                "portfolio_engine shares_to_buy",
            ],
            "passed": gate2["passed"] and bool(FINRA_ROWS_BY_TICKER),
        },
        "gate3": {
            "new_filter_added": False,
            "signals_generated_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_generated_sum"
            ],
            "signals_survived_delta": selected["delta_metrics"]["aggregate_delta"][
                "signals_survived_sum"
            ],
            "minimum_after_survival_rate": selected["delta_metrics"][
                "aggregate_after"
            ]["survival_rate_min"],
            "passed": selected["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ]
            >= 0.05,
        },
        "gate4": selected["gate4"],
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "adjustments": selected["adjustments"],
        "changed_trades": selected["changed_trades"],
        "sizing_attribution": selected["sizing_attribution"],
        "sweep_summary": _sweep_summary(candidates),
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft-ranking and SEC semantic branches remain data-limited; "
                "this deterministic FINRA allocation state avoids those blockers."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If accepted, add a shared FINRA publication-lag adapter/cache and "
                "shared risk_engine/portfolio_engine state used by both backtester.py "
                "and run.py, then rerun all three canonical windows."
            ),
        },
        "why_not_other_changes": (
            "This avoids LLM/SEC soft-ranking because the current archived semantic "
            "fields are sparse, avoids Space/source/ATR nearby retunes after recent "
            "rejections, and avoids candidate-pool expansion because the latest "
            "breadth expansion added noise and old-window regression."
        ),
        "known_risks": [
            "High short crowding can also mark squeeze potential, so a haircut may clip valid momentum winners.",
            "FINRA is biweekly and delayed; it is PIT-safe but stale relative to daily price action.",
            "Borrow fee, shares available, hard-to-borrow, and short-interest-float fields are unavailable in the official CSV.",
            "A positive replay scout is not production-tradable until a shared FINRA adapter and parity tests are added.",
        ],
        "interpretation": interpretation,
        "rejection_reason": None if selected["passed"] else interpretation,
        "next_evidence_needed": (
            None
            if selected["passed"]
            else "Do not retry FINRA days-to-cover haircuts without an orthogonal discriminator such as borrow-fee/float-short data or positive event-quality labels."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            "quant/experiments/exp_20260516_035_finra_short_crowding_risk_haircut.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"docs/experiments/logs/{EXPERIMENT_ID}.json",
            f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
            f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def main() -> dict[str, Any]:
    result = run()
    base.persist(result)
    return result


if __name__ == "__main__":
    result = main()
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "affected_signal_count": result["gate4"]["affected_signal_count"],
                "affected_windows": result["gate4"]["affected_windows"],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
