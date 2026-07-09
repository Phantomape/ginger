"""exp-20260708-020: BTC crypto sleeve realized-vol target overlay.

Alpha-search replay of one fixed policy candidate.  The question is whether a
realized-volatility target overlay on top of the existing BTC daily trend target
improves the current shared crypto sleeve policy without retuning EMA/SMA trend
thresholds.  This runner changes no production crypto advice by itself.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260708-020"
OWNER = "alpha-explore"
SLUG = "crypto_sleeve_vol_target_overlay"
RUNNER = f"quant/experiments/exp_20260708_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PRIOR_BARS = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260708-019"
    / "btc_usd_daily_closes.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260708_020_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Crypto sleeve risk-allocation alpha: applying a fixed realized-volatility "
    "target overlay to the existing BTC daily trend target should improve "
    "risk-adjusted EV versus the current crypto sleeve policy and fee-aware "
    "buy-and-hold across predeclared multi-year BTC windows, without retuning "
    "EMA/SMA trend thresholds."
)
CHANGE_TYPE = "risk_allocation"
IMPLEMENTATION_MODE = "experiment_local_shared_policy_candidate_replay"
MECHANISM_FAMILY = "production_visible_crypto_sleeve_policy"
TRIAL_FAMILY = "btc_spot_crypto_sleeve_realized_vol_target_overlay"
TRIAL_VARIANT_ID = "btc_daily_2017_2026_vol_target_v1"
CHANGED_VARIABLE = "crypto_sleeve_realized_vol_target_overlay_policy_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_shared_policy_change"
NEW_EVIDENCE_AXIS = (
    "New gate shape: a fixed realized-volatility target overlay evaluated as "
    "a separate shared-policy candidate against both the current crypto_sleeve "
    "policy and fee-aware buy-and-hold on the exp-20260708-019 multi-year BTC "
    "history; this is not an EMA/SMA span, trend threshold, target percentage, "
    "or snapshot activation retune."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260708-019", "exp-20260708-010"]
CAUSAL_COMPONENTS = [
    "current crypto trend target",
    "fixed realized-volatility target overlay",
    "historical crypto replay",
    "current-policy comparator",
    "fee-aware buy-and-hold comparator",
    "no production behavior change unless promoted separately",
]
PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 2.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "bull_market_underexposure",
        "volatility_target_whipsaw",
        "current_policy_not_beaten",
        "drawdown_not_improved",
    ],
    "confidence_reason": (
        "The exp-20260708-019 shared historical replay showed the current "
        "trend policy beats buy-and-hold on two bear-containing windows but "
        "lags in the 2023-2026 bull window; a volatility target is a distinct "
        "risk-allocation gate shape that may reduce drawdown/whipsaw, but it "
        "can easily underexpose bull markets."
    ),
    "recorded_at": "2026-07-08T17:04:35+00:00",
}

WINDOWS = [
    {"label": "bull_bear_2017_2019", "start": "2017-01-01", "end": "2019-12-31"},
    {"label": "covid_cycle_2020_2022", "start": "2020-01-01", "end": "2022-12-31"},
    {"label": "current_cycle_2023_2026", "start": "2023-01-01", "end": "2026-07-07"},
]
CONFIG = {
    "annualization_days": 365,
    "fee_pct_per_side": 0.0049,
    "min_rebalance_delta_pct": 0.10,
    "initial_position_pct": 0.0,
    "vol_lookback_days": 30,
    "target_annual_vol": 0.60,
    "min_vol_multiplier": 0.35,
    "max_vol_multiplier": 1.00,
    "min_bars_per_window": 300,
    "aggregate_start": "2017-01-01",
    "acceptance_rule": (
        "Gate 4 passes only if the vol-target overlay beats the current crypto "
        "policy on expected_value_score in >=2/3 fixed windows, has max "
        "drawdown no worse than current policy in every fixed window, improves "
        "aggregate EV versus current policy, remains positive on aggregate "
        "total return, and still beats fee-aware buy-and-hold EV in >=2/3 "
        "windows."
    ),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
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
            mean_ret / stdev * math.sqrt(CONFIG["annualization_days"])
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


def load_prior_decision_rows() -> list[dict[str, Any]]:
    payload = read_json(PRIOR_BARS, {})
    rows = []
    for row in payload.get("rows") or []:
        rows.append(
            {
                "date": str(row["date"]),
                "close": float(row["close"]),
                "state": str(row.get("state") or ""),
                "base_target_position_pct": float(row.get("target_position_pct") or 0.0),
            }
        )
    rows.sort(key=lambda item: item["date"])
    returns: list[float] = []
    for index, row in enumerate(rows):
        if index == 0:
            row["daily_return"] = None
            row["realized_vol_30d"] = None
            row["vol_multiplier"] = 1.0
            row["overlay_target_position_pct"] = row["base_target_position_pct"]
            continue
        prev_close = rows[index - 1]["close"]
        ret = row["close"] / prev_close - 1.0 if prev_close else 0.0
        row["daily_return"] = ret
        returns.append(ret)
        if len(returns) >= CONFIG["vol_lookback_days"]:
            sample = returns[-CONFIG["vol_lookback_days"] :]
            realized = statistics.stdev(sample) * math.sqrt(CONFIG["annualization_days"])
            multiplier = CONFIG["target_annual_vol"] / realized if realized > 0 else 1.0
            multiplier = max(CONFIG["min_vol_multiplier"], min(CONFIG["max_vol_multiplier"], multiplier))
            row["realized_vol_30d"] = realized
            row["vol_multiplier"] = multiplier
            row["overlay_target_position_pct"] = row["base_target_position_pct"] * multiplier
        else:
            row["realized_vol_30d"] = None
            row["vol_multiplier"] = 1.0
            row["overlay_target_position_pct"] = row["base_target_position_pct"]
    return rows


def simulate_segment(
    rows: list[dict[str, Any]],
    target_field: str,
    label: str,
) -> dict[str, Any]:
    if len(rows) < 2:
        return {
            "label": label,
            "bars": len(rows),
            "metrics": summarize_returns(label, []),
            "target_switches": 0,
            "insufficient_bars": True,
        }

    fee = float(CONFIG["fee_pct_per_side"])
    min_delta = float(CONFIG["min_rebalance_delta_pct"])
    position = float(CONFIG["initial_position_pct"])
    returns: list[float] = []
    target_switches = 0
    fee_sum = 0.0
    position_sum = 0.0

    for index in range(len(rows) - 1):
        row = rows[index]
        nxt = rows[index + 1]
        btc_return = nxt["close"] / row["close"] - 1.0
        desired = float(row[target_field])
        delta = desired - position
        rebalance_fee = 0.0
        if abs(delta) >= min_delta:
            rebalance_fee = abs(delta) * fee
            position = desired
            target_switches += 1
        returns.append(position * btc_return - rebalance_fee)
        position_sum += position
        fee_sum += rebalance_fee

    terminal_fee = abs(position) * fee
    if returns and terminal_fee > 0:
        returns[-1] -= terminal_fee
        fee_sum += terminal_fee

    intervals = len(returns)
    return {
        "label": label,
        "bars": len(rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "intervals": intervals,
        "metrics": summarize_returns(label, returns),
        "target_switches": target_switches,
        "avg_position_pct": rounded(position_sum / intervals if intervals else 0.0),
        "fee_cost_pct_sum": rounded(fee_sum),
        "terminal_liquidation_fee_pct": rounded(terminal_fee),
        "insufficient_bars": False,
    }


def simulate_buy_hold(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if len(rows) < 2:
        return {
            "label": label,
            "bars": len(rows),
            "metrics": summarize_returns(label, []),
            "insufficient_bars": True,
        }
    fee = float(CONFIG["fee_pct_per_side"])
    returns = []
    for index in range(len(rows) - 1):
        row = rows[index]
        nxt = rows[index + 1]
        btc_return = nxt["close"] / row["close"] - 1.0
        entry_fee = fee if index == 0 else 0.0
        exit_fee = fee if index == len(rows) - 2 else 0.0
        returns.append(btc_return - entry_fee - exit_fee)
    return {
        "label": label,
        "bars": len(rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "intervals": len(returns),
        "metrics": summarize_returns(label, returns),
        "insufficient_bars": False,
    }


def compare_metrics(a: dict[str, Any], b: dict[str, Any]) -> dict[str, float | None]:
    ma = a["metrics"]
    mb = b["metrics"]
    return {
        "total_return_pct": rounded(ma["total_return_pct"] - mb["total_return_pct"]),
        "expected_value_score": rounded(ma["expected_value_score"] - mb["expected_value_score"]),
        "sharpe_daily": rounded(ma["sharpe_daily"] - mb["sharpe_daily"]),
        "max_drawdown_pct": rounded(ma["max_drawdown_pct"] - mb["max_drawdown_pct"]),
    }


def window_rows(rows: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    return [row for row in rows if start <= row["date"] <= end]


def build_window_result(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    current = simulate_segment(rows, "base_target_position_pct", "current_policy")
    overlay = simulate_segment(rows, "overlay_target_position_pct", "vol_target_overlay")
    buy_hold = simulate_buy_hold(rows, "buy_hold")
    vol_ready = [r for r in rows if r.get("realized_vol_30d") is not None]
    throttled = [
        r
        for r in vol_ready
        if r["base_target_position_pct"] > 0 and r["overlay_target_position_pct"] < r["base_target_position_pct"]
    ]
    return {
        "label": label,
        "bars": len(rows),
        "current_policy": current,
        "vol_target_overlay": overlay,
        "buy_hold": buy_hold,
        "delta_overlay_vs_current": compare_metrics(overlay, current),
        "delta_overlay_vs_buy_hold": compare_metrics(overlay, buy_hold),
        "vol_overlay_attribution": {
            "vol_ready_rows": len(vol_ready),
            "throttled_risk_on_rows": len(throttled),
            "avg_vol_multiplier_on_risk_rows": rounded(
                statistics.fmean(r["vol_multiplier"] for r in throttled)
                if throttled
                else 1.0
            ),
            "min_vol_multiplier_on_risk_rows": rounded(
                min((r["vol_multiplier"] for r in throttled), default=1.0)
            ),
        },
    }


def build_gate4(window_results: list[dict[str, Any]], aggregate: dict[str, Any]) -> dict[str, Any]:
    usable_windows = [
        w
        for w in window_results
        if w["bars"] >= CONFIG["min_bars_per_window"]
        and not w["vol_target_overlay"]["insufficient_bars"]
    ]
    overlay_ev_beats_current = [
        w["label"]
        for w in usable_windows
        if w["vol_target_overlay"]["metrics"]["expected_value_score"]
        > w["current_policy"]["metrics"]["expected_value_score"]
    ]
    overlay_dd_no_worse_current = [
        w["label"]
        for w in usable_windows
        if w["vol_target_overlay"]["metrics"]["max_drawdown_pct"]
        <= w["current_policy"]["metrics"]["max_drawdown_pct"]
    ]
    overlay_ev_beats_buy_hold = [
        w["label"]
        for w in usable_windows
        if w["vol_target_overlay"]["metrics"]["expected_value_score"]
        > w["buy_hold"]["metrics"]["expected_value_score"]
    ]
    checks = {
        "all_windows_have_enough_bars": len(usable_windows) == len(WINDOWS),
        "overlay_ev_beats_current_in_2_of_3_windows": len(overlay_ev_beats_current) >= 2,
        "overlay_drawdown_no_worse_than_current_all_windows": len(overlay_dd_no_worse_current) == len(WINDOWS),
        "overlay_aggregate_ev_beats_current": aggregate["vol_target_overlay"]["metrics"][
            "expected_value_score"
        ]
        > aggregate["current_policy"]["metrics"]["expected_value_score"],
        "overlay_aggregate_return_positive": aggregate["vol_target_overlay"]["metrics"][
            "total_return_pct"
        ]
        > 0.0,
        "overlay_ev_beats_buy_hold_in_2_of_3_windows": len(overlay_ev_beats_buy_hold) >= 2,
    }
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "acceptance_rule": CONFIG["acceptance_rule"],
        "checks": checks,
        "failed_reasons": failed,
        "overlay_ev_beats_current_windows": overlay_ev_beats_current,
        "overlay_drawdown_no_worse_current_windows": overlay_dd_no_worse_current,
        "overlay_ev_beats_buy_hold_windows": overlay_ev_beats_buy_hold,
        "windows": window_results,
        "aggregate": aggregate,
        "accepted_alpha": False,
        "binding_note": (
            "This runner evaluates a policy candidate but does not alter the "
            "shared production helper. A positive result would be a lead until "
            "the helper/parity path is updated in a separate or extended change."
        ),
    }


def compact_segment(segment: dict[str, Any]) -> dict[str, Any]:
    return {
        "bars": segment["bars"],
        "metrics": segment["metrics"],
        "target_switches": segment.get("target_switches"),
        "avg_position_pct": segment.get("avg_position_pct"),
        "fee_cost_pct_sum": segment.get("fee_cost_pct_sum"),
    }


def compact_gate4(gate4: dict[str, Any]) -> dict[str, Any]:
    aggregate = gate4["aggregate"]
    return {
        "acceptance_rule": gate4["acceptance_rule"],
        "checks": gate4["checks"],
        "failed_reasons": gate4["failed_reasons"],
        "overlay_ev_beats_current_windows": gate4["overlay_ev_beats_current_windows"],
        "overlay_drawdown_no_worse_current_windows": gate4[
            "overlay_drawdown_no_worse_current_windows"
        ],
        "overlay_ev_beats_buy_hold_windows": gate4["overlay_ev_beats_buy_hold_windows"],
        "windows": [
            {
                "label": w["label"],
                "bars": w["bars"],
                "current_policy": compact_segment(w["current_policy"]),
                "vol_target_overlay": compact_segment(w["vol_target_overlay"]),
                "buy_hold": {
                    "bars": w["buy_hold"]["bars"],
                    "metrics": w["buy_hold"]["metrics"],
                },
                "delta_overlay_vs_current": w["delta_overlay_vs_current"],
                "delta_overlay_vs_buy_hold": w["delta_overlay_vs_buy_hold"],
                "vol_overlay_attribution": w["vol_overlay_attribution"],
            }
            for w in gate4["windows"]
        ],
        "aggregate": {
            "label": aggregate["label"],
            "bars": aggregate["bars"],
            "current_policy": compact_segment(aggregate["current_policy"]),
            "vol_target_overlay": compact_segment(aggregate["vol_target_overlay"]),
            "buy_hold": {
                "bars": aggregate["buy_hold"]["bars"],
                "metrics": aggregate["buy_hold"]["metrics"],
            },
            "delta_overlay_vs_current": aggregate["delta_overlay_vs_current"],
            "delta_overlay_vs_buy_hold": aggregate["delta_overlay_vs_buy_hold"],
            "vol_overlay_attribution": aggregate["vol_overlay_attribution"],
        },
        "accepted_alpha": False,
        "binding_note": gate4["binding_note"],
    }


def build_payload() -> dict[str, Any]:
    ticket_before = read_json(TICKET_JSON, {})
    baseline = read_json(BASELINE_RESULT, {}) or {}
    rows = load_prior_decision_rows()
    window_results = [
        build_window_result(window_rows(rows, w["start"], w["end"]), w["label"])
        for w in WINDOWS
    ]
    aggregate_rows = window_rows(rows, CONFIG["aggregate_start"], "9999-12-31")
    aggregate = build_window_result(aggregate_rows, "aggregate_2017_2026")
    gate4 = build_gate4(window_results, aggregate)

    gate4_passed = not gate4["failed_reasons"]
    if gate4_passed:
        status = "observed_only"
        decision = "observed_only_positive_lead_crypto_vol_target_overlay_not_promoted"
        rejection_reason = None
        why = (
            "The fixed volatility target overlay improved the current crypto "
            "policy under the predeclared replay rule, but this runner did not "
            "change the shared production helper, so it is only a policy lead."
        )
        realized_failure = []
        actual_success = 1
    else:
        status = "rejected"
        decision = "rejected_crypto_vol_target_overlay_policy_candidate"
        rejection_reason = ";".join(gate4["failed_reasons"])
        why = (
            "The volatility target overlay did not beat the current crypto "
            "policy under the predeclared multi-window rule: "
            + rejection_reason
        )
        realized_failure = gate4["failed_reasons"]
        actual_success = 0

    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    production_impact = {
        "shared_policy_changed": False,
        "run_adapter_changed": False,
        "backtester_adapter_changed": False,
        "stock_strategy_changed": False,
        "alters_stock_orders": False,
        "alters_crypto_orders": False,
        "trade_enabled": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "parity_note": (
            "Experiment-local replay only; production crypto advice remains "
            "the existing daily EMA20/EMA100/SMA200 trend policy."
        ),
    }
    calibration = {
        "actual_success": actual_success,
        "predicted_success_probability": PREDICTION["success_probability"],
        "brier_score": rounded((PREDICTION["success_probability"] - actual_success) ** 2),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_modes": realized_failure,
        "predicted_failure_mode_hit": any(
            reason
            in {
                "overlay_ev_beats_current_in_2_of_3_windows",
                "overlay_aggregate_ev_beats_current",
            }
            for reason in realized_failure
        ),
        "surprise_note": why,
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "causal_components": CAUSAL_COMPONENTS,
        "prediction": PREDICTION,
        "calibration": calibration,
        "config": {**CONFIG, "windows": WINDOWS},
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "risk_allocation",
            "history_check": {
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "novelty": ticket_before.get("novelty"),
            },
            "single_policy_bundle": CHANGED_VARIABLE,
            "success_failure_standard": CONFIG["acceptance_rule"],
            "reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "stock_strategy_baseline": {
                "baseline_result_file": repo_rel(BASELINE_RESULT),
                "available": bool(baseline),
            },
            "crypto_baselines": [
                "current_crypto_sleeve_policy_from_exp-20260708-019_rows",
                "fee_aware_btc_buy_and_hold",
            ],
            "passed": bool(rows),
        },
        "gate2": {
            "required_fields": [
                "date",
                "close",
                "base_target_position_pct",
                "daily_return",
                "realized_vol_30d",
                "overlay_target_position_pct",
            ],
            "decision_rows": len(rows),
            "first_decision_date": rows[0]["date"] if rows else None,
            "last_decision_date": rows[-1]["date"] if rows else None,
            "entry_date_contract": "not_applicable_crypto_spot_allocation_no_Position_entry",
            "target_price_contract": "not_applicable_crypto_spot_allocation_no_ATR_exit",
            "passed": bool(rows),
        },
        "gate3": {
            "no_filter_added": True,
            "decision_rows": len(rows),
            "window_bar_counts": {w["label"]: w["bars"] for w in window_results},
            "survival_rate": 1.0 if rows else 0.0,
            "passed": bool(rows),
        },
        "gate4": gate4,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune vol lookback, target annual vol, min/max "
                "multipliers, hysteresis, fee assumptions, EMA/SMA spans, or "
                "window boundaries on this same BTC replay to flip the verdict."
            ),
            "new_evidence_required": (
                "A valid retry needs a materially different crypto data source "
                "or asset, a separate shared helper policy with ex-ante "
                "validation, or materially more settled production crypto "
                "forward rows."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "materially different crypto data source or asset",
            "separate shared helper policy with ex-ante validation",
            "materially more settled production crypto forward rows",
        ],
        "changed_files": changed_files,
        "related_files": [
            RUNNER,
            repo_rel(PRIOR_BARS),
            repo_rel(BASELINE_RESULT),
            "quant/crypto_sleeve.py",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "llm_metrics": {"used_llm": False},
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": ticket_before,
        "completed_at": utc_now(),
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": compact_gate4(payload["gate4"]),
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "accepted_alpha": payload["accepted_alpha"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "completed_at": payload["completed_at"],
    }


def format_window_row(row: dict[str, Any]) -> str:
    cur = row["current_policy"]["metrics"]
    over = row["vol_target_overlay"]["metrics"]
    return (
        f"| {row['label']} | {row['bars']} | {cur['expected_value_score']} | "
        f"{over['expected_value_score']} | {row['delta_overlay_vs_current']['expected_value_score']} | "
        f"{cur['max_drawdown_pct']} | {over['max_drawdown_pct']} | "
        f"{cur['total_return_pct']} | {over['total_return_pct']} | "
        f"{row['vol_overlay_attribution']['throttled_risk_on_rows']} |"
    )


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID}: BTC Crypto Sleeve Vol Target Overlay",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Gate 4",
        "",
        "| Window | Bars | Current EV | Overlay EV | EV delta | Current maxDD | Overlay maxDD | Current ret | Overlay ret | Throttled rows |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for window in gate4["windows"]:
        lines.append(format_window_row(window))
    lines.append(format_window_row(gate4["aggregate"]))
    lines.extend(
        [
            "",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            f"- Overlay EV beats current windows: `{', '.join(gate4['overlay_ev_beats_current_windows']) or 'none'}`",
            f"- Drawdown no worse windows: `{', '.join(gate4['overlay_drawdown_no_worse_current_windows']) or 'none'}`",
            "",
            "## Reflection",
            "",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_record = compact_log_record(payload)
    ticket = dict(payload["ticket_before"] or {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["completed_at"],
            "result": {
                "decision": payload["decision"],
                "accepted": payload["accepted"],
                "accepted_alpha": payload["accepted_alpha"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "gate4": log_record["gate4"],
            },
        }
    )

    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    write_json(TICKET_JSON, ticket)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": log_record["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": log_record["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
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
                "gate4": compact_gate4(payload["gate4"]),
                "artifact": payload["artifact"],
                "log": payload["log"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
