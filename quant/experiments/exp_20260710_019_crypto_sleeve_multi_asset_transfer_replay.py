"""exp-20260710-019: batched non-BTC crypto sleeve transfer replay.

Observed-only alpha attribution. The single question is whether the existing
production crypto sleeve target policy (EMA20/EMA100/SMA200 daily trend
switch, unchanged spans, targets, fees, and hysteresis) transfers across a
predeclared batch of non-BTC spot crypto assets. This is intentionally batched:
exp-20260710-017 forbids one-altcoin-per-ID continuation under the same recipe.

The runner changes no shared policy, live config, stock order, crypto order,
ranking, sizing, exit rule, prompt, or production adapter.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from crypto_sleeve import (  # noqa: E402
    DEFAULT_CRYPTO_CONFIG,
    completed_daily_bars,
    compute_crypto_indicators,
    decide_crypto_target,
    fetch_crypto_ohlcv,
    load_crypto_config,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260710-019"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "crypto_sleeve_multi_asset_transfer_replay"
RUNNER = f"quant/experiments/exp_20260710_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_019_{SLUG}.json"
BARS_JSON = OUT_DIR / "non_btc_crypto_daily_decision_rows.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: replay the unchanged production crypto sleeve daily "
    "EMA20/EMA100/SMA200 target policy as a single batched transfer test across "
    "multiple non-BTC crypto spot assets, using each asset's own fee-aware "
    "buy-and-hold comparator; the goal is to test cross-asset generalization "
    "without retuning spans, fees, windows, or target percentages."
)
CHANGE_TYPE = "risk_allocation"
IMPLEMENTATION_MODE = "observed_only_shared_policy_historical_replay"
MECHANISM_FAMILY = "production_visible_crypto_sleeve_historical_replay"
TRIAL_FAMILY = "crypto_sleeve_multi_asset_transfer_replay"
TRIAL_VARIANT_ID = "non_btc_spot_batch_v1"
SINGLE_CAUSAL_VARIABLE = "crypto_sleeve_batched_non_btc_spot_transfer_replay_v1"
NEW_EVIDENCE_TYPE = "new_data_source_batched_non_btc_crypto_histories"
NEW_EVIDENCE_AXIS = (
    "New data source and legal batched gate shape: multiple non-BTC crypto spot "
    "daily histories evaluated together in one predeclared batch, the exact "
    "follow-up shape required by exp-20260710-017; no one-coin-per-ID sweep or "
    "policy retune."
)
NEARBY_PRIORS = [
    "exp-20260710-017",
    "exp-20260708-019",
    "exp-20260708-020",
    "exp-20260708-010",
]
CAUSAL_COMPONENTS = [
    "shared production crypto policy functions",
    "multiple non-BTC spot daily histories",
    "fee-aware per-asset buy-and-hold comparators",
    "fixed batched acceptance rule",
    "no production behavior change",
]
ACCEPTANCE_RULE = (
    "Observed-only positive lead only if the unchanged shared crypto policy "
    "beats fee-aware buy-and-hold EV in at least 2 of 3 windows for a majority "
    "of fetched non-BTC assets, improves drawdown for every evaluated asset, "
    "and aggregate cross-asset policy return is positive; no production "
    "behavior changes."
)

ASSETS = [
    {"symbol": "ETH-USD", "display": "ETH/USD", "prior": "exp-20260710-017 sanity asset"},
    {"symbol": "SOL-USD", "display": "SOL/USD", "prior": "new asset"},
    {"symbol": "XRP-USD", "display": "XRP/USD", "prior": "new asset"},
    {"symbol": "ADA-USD", "display": "ADA/USD", "prior": "new asset"},
    {"symbol": "BNB-USD", "display": "BNB/USD", "prior": "new asset"},
    {"symbol": "DOGE-USD", "display": "DOGE/USD", "prior": "new asset"},
    {"symbol": "LTC-USD", "display": "LTC/USD", "prior": "new asset"},
    {"symbol": "LINK-USD", "display": "LINK/USD", "prior": "new asset"},
]
WINDOWS = [
    {"label": "crypto_bear_2021_2022", "start": "2021-05-01", "end": "2022-12-31"},
    {"label": "post_bear_recovery_2023_2024", "start": "2023-01-01", "end": "2024-12-31"},
    {"label": "current_cycle_2025_2026", "start": "2025-01-01", "end": "2026-07-09"},
]
AGGREGATE_START = "2021-05-01"
MIN_FETCHED_ASSETS = 4
MIN_BARS_PER_WINDOW = 250
MIN_TARGET_SWITCHES_AGGREGATE = 4
LOOKBACK_DAYS = 2600
ANNUALIZATION_DAYS = 365
INITIAL_POSITION_PCT = 0.0

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "yfinance_multi_asset_history_unavailable",
        "buy_and_hold_beats_policy_in_bull_windows",
        "fees_and_whipsaw_consume_edge",
        "asset_selection_fragility",
        "batch_contains_too_few_assets",
    ],
    "confidence_reason": (
        "Mechanism: daily trend filters should reduce crypto drawdowns, but ETH "
        "just failed the EV transfer rule and buy-and-hold often dominates bull "
        "windows. This is still a legal follow-up because exp-20260710-017 "
        "explicitly forbade one-coin-per-ID sweeps and required any altcoin "
        "continuation to be a single batched experiment."
    ),
    "recorded_at": "2026-07-10T18:05:29+00:00",
}

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260710-019/exp_20260710_019_crypto_sleeve_multi_asset_transfer_replay.json",
    "data/experiments/exp-20260710-019/non_btc_crypto_daily_decision_rows.json",
    "experiments/logs/exp-20260710-019.json",
    "experiments/cards/exp-20260710-019.md",
    "experiments/artifacts/exp-20260710-019_crypto_sleeve_multi_asset_transfer_replay.md",
    "experiments/manifests/exp-20260710-019.json",
    "experiments/tickets/exp-20260710-019.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rounded(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return round(float(value), digits)


def equity_curve(returns: list[float]) -> list[float]:
    curve = [1.0]
    for ret in returns:
        curve.append(curve[-1] * (1.0 + ret))
    return curve


def max_drawdown(curve: list[float]) -> float:
    peak = curve[0] if curve else 1.0
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return abs(worst)


def summarize_returns(label: str, returns: list[float]) -> dict[str, Any]:
    curve = equity_curve(returns)
    total_return = curve[-1] - 1.0 if curve else 0.0
    if len(returns) > 1:
        mean_ret = statistics.fmean(returns)
        stdev = statistics.stdev(returns)
        sharpe = (
            mean_ret / stdev * math.sqrt(ANNUALIZATION_DAYS)
            if stdev > 0
            else 0.0
        )
    else:
        mean_ret = returns[0] if returns else 0.0
        stdev = 0.0
        sharpe = 0.0
    return {
        "label": label,
        "periods": len(returns),
        "total_return_pct": rounded(total_return),
        "expected_value_score": rounded(total_return * sharpe),
        "sharpe_daily": rounded(sharpe),
        "mean_period_return_pct": rounded(mean_ret),
        "vol_period_return_pct": rounded(stdev),
        "max_drawdown_pct": rounded(max_drawdown(curve)),
        "win_rate": rounded(
            sum(1 for ret in returns if ret > 0) / len(returns) if returns else 0.0
        ),
        "ending_equity": rounded(curve[-1] if curve else 1.0),
    }


def build_decision_rows(df) -> list[dict[str, Any]]:
    with_indicators = compute_crypto_indicators(df)
    ready = with_indicators.dropna(subset=["ema20", "ema100", "sma200"])
    rows: list[dict[str, Any]] = []
    for idx, row in ready.iterrows():
        snapshot = {
            "close": float(row["close"]),
            "ema20": float(row["ema20"]),
            "ema100": float(row["ema100"]),
            "sma200": float(row["sma200"]),
        }
        target = decide_crypto_target(snapshot)
        rows.append(
            {
                "date": idx.date().isoformat(),
                "close": float(row["close"]),
                "state": target["state"],
                "target_position_pct": float(target["target_position_pct"]),
            }
        )
    return rows


def simulate_segment(
    rows: list[dict[str, Any]],
    fee: float,
    min_rebalance_delta_pct: float,
    label: str,
) -> dict[str, Any]:
    if len(rows) < 2:
        return {
            "label": label,
            "bars": len(rows),
            "policy": summarize_returns("policy", []),
            "buy_hold": summarize_returns("buy_hold", []),
            "target_switches": 0,
            "insufficient_bars": True,
        }

    position = float(INITIAL_POSITION_PCT)
    policy_returns: list[float] = []
    buy_hold_returns: list[float] = []
    target_switches = 0
    policy_fee_sum = 0.0
    buy_hold_fee_sum = 0.0
    position_sum = 0.0
    state_counts: dict[str, int] = {}

    for index in range(len(rows) - 1):
        row = rows[index]
        nxt = rows[index + 1]
        asset_return = nxt["close"] / row["close"] - 1.0
        desired = float(row["target_position_pct"])
        delta = desired - position
        rebalance_fee = 0.0
        if abs(delta) >= min_rebalance_delta_pct:
            rebalance_fee = abs(delta) * fee
            position = desired
            target_switches += 1
        policy_returns.append(position * asset_return - rebalance_fee)
        buy_hold_fee = fee if index == 0 else 0.0
        if index == len(rows) - 2:
            buy_hold_fee += fee
        buy_hold_returns.append(asset_return - buy_hold_fee)
        policy_fee_sum += rebalance_fee
        buy_hold_fee_sum += buy_hold_fee
        position_sum += position
        state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1

    terminal_fee = abs(position) * fee
    if terminal_fee > 0 and policy_returns:
        policy_returns[-1] -= terminal_fee
        policy_fee_sum += terminal_fee

    policy = summarize_returns("policy", policy_returns)
    buy_hold = summarize_returns("buy_hold", buy_hold_returns)
    intervals = len(policy_returns)
    return {
        "label": label,
        "bars": len(rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "intervals": intervals,
        "target_switches": target_switches,
        "avg_position_pct": rounded(position_sum / intervals if intervals else 0.0),
        "policy_fee_cost_pct_sum": rounded(policy_fee_sum),
        "buy_hold_fee_cost_pct_sum": rounded(buy_hold_fee_sum),
        "terminal_policy_liquidation_fee_pct": rounded(terminal_fee),
        "state_counts": state_counts,
        "policy": policy,
        "buy_hold": buy_hold,
        "delta_vs_buy_hold": {
            "total_return_pct": rounded(
                policy["total_return_pct"] - buy_hold["total_return_pct"]
            ),
            "expected_value_score": rounded(
                policy["expected_value_score"] - buy_hold["expected_value_score"]
            ),
            "sharpe_daily": rounded(policy["sharpe_daily"] - buy_hold["sharpe_daily"]),
            "max_drawdown_pct": rounded(
                policy["max_drawdown_pct"] - buy_hold["max_drawdown_pct"]
            ),
        },
        "insufficient_bars": False,
    }


def evaluate_asset(
    asset: Mapping[str, str],
    fee: float,
    min_rebalance_delta_pct: float,
) -> dict[str, Any]:
    symbol = asset["symbol"]
    try:
        ohlcv = fetch_crypto_ohlcv(symbol=symbol, lookback_days=LOOKBACK_DAYS)
        completed = completed_daily_bars(ohlcv)
        rows = build_decision_rows(completed)
    except Exception as exc:  # network/vendor failures are evidence, not crashes
        return {
            "symbol": symbol,
            "display": asset.get("display", symbol),
            "prior": asset.get("prior"),
            "fetched": False,
            "error": repr(exc),
            "rows": 0,
        }

    window_results = []
    for window in WINDOWS:
        window_rows = [
            row
            for row in rows
            if window["start"] <= row["date"] <= window["end"]
        ]
        window_results.append(
            simulate_segment(
                window_rows,
                fee,
                min_rebalance_delta_pct,
                window["label"],
            )
        )
    aggregate_rows = [row for row in rows if row["date"] >= AGGREGATE_START]
    aggregate = simulate_segment(
        aggregate_rows,
        fee,
        min_rebalance_delta_pct,
        f"{symbol}_aggregate",
    )
    ev_wins = [
        item["label"]
        for item in window_results
        if not item["insufficient_bars"]
        and item["policy"]["expected_value_score"] > item["buy_hold"]["expected_value_score"]
    ]
    dd_wins = [
        item["label"]
        for item in window_results
        if not item["insufficient_bars"]
        and item["policy"]["max_drawdown_pct"] < item["buy_hold"]["max_drawdown_pct"]
    ]
    enough_bars = all(item["bars"] >= MIN_BARS_PER_WINDOW for item in window_results)
    asset_passed = (
        enough_bars
        and len(ev_wins) >= 2
        and len(dd_wins) == len(WINDOWS)
        and aggregate["policy"]["total_return_pct"] > 0
        and aggregate["target_switches"] >= MIN_TARGET_SWITCHES_AGGREGATE
    )
    return {
        "symbol": symbol,
        "display": asset.get("display", symbol),
        "prior": asset.get("prior"),
        "fetched": True,
        "rows": len(rows),
        "first_decision_date": rows[0]["date"] if rows else None,
        "last_decision_date": rows[-1]["date"] if rows else None,
        "windows": window_results,
        "aggregate": aggregate,
        "ev_winning_windows": ev_wins,
        "drawdown_winning_windows": dd_wins,
        "checks": {
            "all_windows_have_enough_bars": enough_bars,
            "ev_beats_buy_hold_in_2_of_3_windows": len(ev_wins) >= 2,
            "drawdown_below_buy_hold_in_all_windows": len(dd_wins) == len(WINDOWS),
            "aggregate_policy_total_return_positive": aggregate["policy"][
                "total_return_pct"
            ]
            > 0,
            "aggregate_has_target_switches": aggregate["target_switches"]
            >= MIN_TARGET_SWITCHES_AGGREGATE,
        },
        "passed_asset_rule": asset_passed,
    }


def build_gate4(assets: list[dict[str, Any]]) -> dict[str, Any]:
    fetched = [item for item in assets if item.get("fetched")]
    passed_assets = [item for item in fetched if item.get("passed_asset_rule")]
    failed_fetches = [item for item in assets if not item.get("fetched")]
    enough_assets = len(fetched) >= MIN_FETCHED_ASSETS
    majority_assets_passed = len(passed_assets) > (len(fetched) / 2) if fetched else False
    all_fetched_drawdown_passed = all(
        len(item.get("drawdown_winning_windows") or []) == len(WINDOWS)
        for item in fetched
    )
    aggregate_policy_returns = [
        item["aggregate"]["policy"]["total_return_pct"] for item in fetched
    ]
    aggregate_policy_return_sum = sum(aggregate_policy_returns)
    aggregate_positive = aggregate_policy_return_sum > 0
    checks = {
        "fetched_assets_gte_min": enough_assets,
        "majority_assets_pass_asset_rule": majority_assets_passed,
        "all_fetched_assets_drawdown_win_all_windows": all_fetched_drawdown_passed,
        "aggregate_cross_asset_policy_return_positive": aggregate_positive,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if not enough_assets:
        decision = "observed_only_blocked_crypto_sleeve_multi_asset_data_unavailable"
    elif failed:
        decision = "observed_only_rejected_crypto_sleeve_multi_asset_transfer_replay"
    else:
        decision = "observed_only_positive_lead_crypto_sleeve_multi_asset_transfer_replay"
    return {
        "benchmark": "fee_aware_buy_and_hold_per_asset",
        "acceptance_rule": ACCEPTANCE_RULE,
        "checks": checks,
        "failed_reasons": failed,
        "decision": decision,
        "accepted_alpha": False,
        "observed_only_lead": not failed and enough_assets,
        "asset_count": len(assets),
        "fetched_asset_count": len(fetched),
        "min_fetched_assets": MIN_FETCHED_ASSETS,
        "passed_asset_count": len(passed_assets),
        "passed_assets": [item["symbol"] for item in passed_assets],
        "failed_fetches": [
            {"symbol": item["symbol"], "error": item.get("error")}
            for item in failed_fetches
        ],
        "aggregate_cross_asset_policy_return_sum": rounded(aggregate_policy_return_sum),
        "assets": assets,
        "binding_acceptance_note": (
            "Observed-only batched transfer replay through unchanged shared "
            "crypto policy functions. A positive result would still require a "
            "separate default-off shared policy experiment before any "
            "production crypto expansion."
        ),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, Mapping) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "available": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": (
            round(max(float(row.get("max_drawdown_pct") or 0.0) for row in windows), 4)
            if windows
            else None
        ),
    }


def build_payload() -> dict[str, Any]:
    crypto_config = load_crypto_config()
    fee = float(
        crypto_config.get("fee_pct_per_side")
        or DEFAULT_CRYPTO_CONFIG["fee_pct_per_side"]
    )
    min_delta = float(
        crypto_config.get("min_rebalance_delta_pct")
        or DEFAULT_CRYPTO_CONFIG["min_rebalance_delta_pct"]
    )
    asset_results = [evaluate_asset(asset, fee, min_delta) for asset in ASSETS]
    gate4 = build_gate4(asset_results)
    baseline = baseline_metrics()
    success = bool(gate4["observed_only_lead"])
    blocked = gate4["decision"].startswith("observed_only_blocked")
    if success:
        rejection_reason = None
        why = (
            "The unchanged daily crypto trend policy transferred across the "
            "predeclared non-BTC batch under the majority-asset EV, all-asset "
            "drawdown, and aggregate-return gates."
        )
    elif blocked:
        rejection_reason = "fetched_assets_below_minimum"
        why = (
            "The batch could not fetch enough predeclared non-BTC asset "
            "histories to evaluate the transfer rule."
        )
    else:
        rejection_reason = ";".join(gate4["failed_reasons"])
        why = (
            "The unchanged daily crypto trend policy did not transfer under "
            "the predeclared batched rule: " + rejection_reason
        )

    p = float(PREDICTION["success_probability"])
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": gate4["decision"],
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": success,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": gate4["decision"],
            "actual_success": int(success),
            "predicted_success_probability": p,
            "brier_score": round((p - (1.0 if success else 0.0)) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": gate4["failed_reasons"],
            "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
            "surprise_note": why,
        },
        "config": {
            "assets": ASSETS,
            "windows": WINDOWS,
            "aggregate_start": AGGREGATE_START,
            "lookback_days": LOOKBACK_DAYS,
            "annualization_days": ANNUALIZATION_DAYS,
            "min_fetched_assets": MIN_FETCHED_ASSETS,
            "min_bars_per_window": MIN_BARS_PER_WINDOW,
            "min_target_switches_aggregate": MIN_TARGET_SWITCHES_AGGREGATE,
            "fee_pct_per_side": fee,
            "min_rebalance_delta_pct": min_delta,
        },
        "crypto_config": {
            "production_symbol": crypto_config.get("symbol"),
            "production_policy": crypto_config.get("policy"),
            "fee_pct_per_side": fee,
            "min_rebalance_delta_pct": min_delta,
            "note": (
                "Production config remains unchanged; non-BTC assets borrow "
                "the same policy, fee, and hysteresis semantics for "
                "observed-only transfer replay."
            ),
        },
        "before_metrics": baseline,
        "after_metrics": {
            **baseline,
            "fetched_asset_count": gate4["fetched_asset_count"],
            "passed_asset_count": gate4["passed_asset_count"],
            "observed_only_lead": success,
        },
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "observed_only_lead": success,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "stock_strategy_baseline_available": BASELINE_RESULT.exists(),
            "crypto_baselines": ["fee_aware_buy_and_hold_per_asset"],
        },
        "gate2": {
            "passed": gate4["fetched_asset_count"] > 0,
            "required_fields": ["date", "close", "state", "target_position_pct"],
            "fetched_asset_count": gate4["fetched_asset_count"],
            "entry_date_contract": "not_applicable_crypto_spot_allocation_no_Position_entry",
            "target_price_contract": "not_applicable_crypto_spot_allocation_no_ATR_exit",
            "shared_policy_functions": [
                "quant/crypto_sleeve.py:compute_crypto_indicators",
                "quant/crypto_sleeve.py:decide_crypto_target",
            ],
        },
        "gate3": {
            "passed": True,
            "no_filter_added": True,
            "survival_rate": 1.0 if gate4["fetched_asset_count"] else 0.0,
        },
        "gate4": gate4,
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "stock_strategy_changed": False,
            "alters_stock_orders": False,
            "alters_crypto_orders": False,
            "existing_production_crypto_advice_unchanged": True,
            "model_trained": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only historical transfer replay through the same shared "
                "policy functions; production crypto sleeve remains BTC-only."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun this batch by changing asset list, EMA/SMA spans, "
                "target percentages, hysteresis, fee assumptions, window "
                "boundaries, annualization, or majority thresholds to flip the "
                "verdict. Do not continue consuming altcoins one ID at a time."
            ),
            "new_evidence_required": (
                "A valid crypto retry needs materially more saved production "
                "crypto forward snapshots, a genuinely different crypto data "
                "source such as venue/execution cost or liquidity evidence, or "
                "a separately predeclared shared policy family."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "materially_more_saved_production_crypto_forward_snapshots",
            "or_genuinely_different_crypto_execution_cost_or_liquidity_source",
            "or_separately_predeclared_shared_policy_family",
        ],
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260710-017 rejected ETH transfer and forbade one-coin-"
                "per-ID sweeps; this run is the predeclared batched shape."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": CHANGED_FILES + ["quant/crypto_sleeve.py"],
        "changed_files": CHANGED_FILES,
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "bars_artifact": repo_rel(BARS_JSON),
        "report": repo_rel(ARTIFACT_MD),
        "log": repo_rel(LOG_JSON),
    }
    return payload


def compact_asset(asset: Mapping[str, Any]) -> dict[str, Any]:
    if not asset.get("fetched"):
        return {
            "symbol": asset.get("symbol"),
            "display": asset.get("display"),
            "fetched": False,
            "error": asset.get("error"),
        }
    return {
        "symbol": asset["symbol"],
        "display": asset.get("display"),
        "fetched": True,
        "rows": asset.get("rows"),
        "first_decision_date": asset.get("first_decision_date"),
        "last_decision_date": asset.get("last_decision_date"),
        "ev_winning_windows": asset.get("ev_winning_windows"),
        "drawdown_winning_windows": asset.get("drawdown_winning_windows"),
        "passed_asset_rule": asset.get("passed_asset_rule"),
        "checks": asset.get("checks"),
        "aggregate": {
            "policy": asset["aggregate"]["policy"],
            "buy_hold": asset["aggregate"]["buy_hold"],
            "delta_vs_buy_hold": asset["aggregate"]["delta_vs_buy_hold"],
            "target_switches": asset["aggregate"].get("target_switches"),
            "avg_position_pct": asset["aggregate"].get("avg_position_pct"),
        },
        "windows": [
            {
                "label": item["label"],
                "bars": item["bars"],
                "policy": item["policy"],
                "buy_hold": item["buy_hold"],
                "delta_vs_buy_hold": item.get("delta_vs_buy_hold"),
                "target_switches": item.get("target_switches"),
                "avg_position_pct": item.get("avg_position_pct"),
            }
            for item in asset.get("windows") or []
        ],
    }


def build_log_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "owner": OWNER,
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": {
            "benchmark": gate4["benchmark"],
            "acceptance_rule": gate4["acceptance_rule"],
            "checks": gate4["checks"],
            "failed_reasons": gate4["failed_reasons"],
            "decision": gate4["decision"],
            "observed_only_lead": gate4["observed_only_lead"],
            "fetched_asset_count": gate4["fetched_asset_count"],
            "passed_asset_count": gate4["passed_asset_count"],
            "passed_assets": gate4["passed_assets"],
            "failed_fetches": gate4["failed_fetches"],
            "aggregate_cross_asset_policy_return_sum": gate4[
                "aggregate_cross_asset_policy_return_sum"
            ],
            "assets": [compact_asset(asset) for asset in gate4["assets"]],
            "accepted_alpha": False,
            "binding_acceptance_note": gate4["binding_acceptance_note"],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": True,
        "artifact": payload["artifact"],
        "bars_artifact": payload["bars_artifact"],
        "report": payload["report"],
        "log": payload["log"],
    }


def build_bars_artifact(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows_by_asset: dict[str, Any] = {}
    for asset in payload["gate4"]["assets"]:
        rows_by_asset[asset["symbol"]] = {
            "fetched": asset.get("fetched"),
            "rows": asset.get("rows"),
            "first_decision_date": asset.get("first_decision_date"),
            "last_decision_date": asset.get("last_decision_date"),
            "error": asset.get("error"),
            "windows": [
                {
                    "label": item["label"],
                    "bars": item["bars"],
                    "first_date": item.get("first_date"),
                    "last_date": item.get("last_date"),
                    "target_switches": item.get("target_switches"),
                    "avg_position_pct": item.get("avg_position_pct"),
                    "state_counts": item.get("state_counts"),
                }
                for item in asset.get("windows") or []
            ],
        }
    return {
        "experiment_id": EXPERIMENT_ID,
        "downloaded_at": payload["timestamp"],
        "source": "yfinance daily via quant.crypto_sleeve.fetch_crypto_ohlcv",
        "config": payload["config"],
        "assets": rows_by_asset,
    }


def asset_markdown_row(asset: Mapping[str, Any]) -> str:
    if not asset.get("fetched"):
        return (
            f"| {asset.get('symbol')} | no | - | - | - | - | "
            f"{asset.get('error')} |"
        )
    aggregate = asset["aggregate"]
    return (
        f"| {asset['symbol']} | yes | {asset.get('passed_asset_rule')} | "
        f"{','.join(asset.get('ev_winning_windows') or []) or 'none'} | "
        f"{','.join(asset.get('drawdown_winning_windows') or []) or 'none'} | "
        f"{aggregate['policy']['total_return_pct']} / "
        f"{aggregate['buy_hold']['total_return_pct']} | "
        f"{';'.join(k for k, ok in asset['checks'].items() if not ok) or 'none'} |"
    )


def build_report(payload: Mapping[str, Any]) -> str:
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID}: Crypto Sleeve Multi-Asset Transfer Replay",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Acceptance rule: {ACCEPTANCE_RULE}",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Asset Results",
        "",
        "| Asset | Fetched | Pass | EV win windows | DD win windows | Aggregate policy/B&H return | Failed checks |",
        "|---|---|---:|---|---|---:|---|",
    ]
    for asset in gate4["assets"]:
        lines.append(asset_markdown_row(asset))
    lines.extend(
        [
            "",
            "## Batch Gate",
            "",
            f"- Fetched assets: `{gate4['fetched_asset_count']}` / `{gate4['asset_count']}`",
            f"- Passed assets: `{gate4['passed_asset_count']}`",
            f"- Failed reasons: `{gate4['failed_reasons']}`",
            f"- Aggregate cross-asset policy return sum: `{gate4['aggregate_cross_asset_policy_return_sum']}`",
            "",
            "## Boundary",
            "",
            f"- Production impact: {payload['production_impact']['parity_note']}",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(payload: Mapping[str, Any]) -> str:
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: crypto sleeve multi-asset transfer replay",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Fetched / passed assets: `{gate4['fetched_asset_count']}` / `{gate4['passed_asset_count']}`",
            f"- Failed reasons: `{gate4['failed_reasons']}`",
            f"- Artifact: `{payload['artifact']}`",
            f"- Report: `{payload['report']}`",
            "- Strategy/live order behavior changed: `false`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "bars_artifact": repo_rel(BARS_JSON),
        "report": repo_rel(ARTIFACT_MD),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_record = build_log_record(payload)
    write_json(OUT_JSON, payload)
    write_json(BARS_JSON, build_bars_artifact(payload))
    save_experiment_log_entry(log_record, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    write_text(ARTIFACT_MD, build_report(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "bars_artifact": repo_rel(BARS_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": log_record["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "changed_variable": SINGLE_CAUSAL_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "acceptance_rule": ACCEPTANCE_RULE,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "bars_artifact": repo_rel(BARS_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": log_record["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": payload["artifact"],
                "fetched_asset_count": payload["gate4"]["fetched_asset_count"],
                "passed_asset_count": payload["gate4"]["passed_asset_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
