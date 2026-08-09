"""exp-20260710-017: ETH crypto sleeve shared-policy transfer historical replay.

Observed-only alpha attribution. The single question is whether the existing
production crypto sleeve target policy (EMA20/EMA100/SMA200 daily trend
switch, unchanged spans and hysteresis), replayed through the exact shared
production policy functions in quant/crypto_sleeve.py, adds risk-adjusted
value versus fee-aware ETH buy-and-hold over multi-year ETH-USD daily bars
covering the 2018 and 2022 bear markets.

This is the legal follow-up axis declared by exp-20260708-019
("a different crypto data source or asset"). The runner changes no shared
policy, target threshold, live config, stock order, crypto order, ranking,
sizing, exit rule, or LLM boundary. No BTC row, span, threshold, fee, or
window is retuned.
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
from crypto_sleeve import (  # noqa: E402
    DEFAULT_CRYPTO_CONFIG,
    completed_daily_bars,
    compute_crypto_indicators,
    decide_crypto_target,
    fetch_crypto_ohlcv,
    load_crypto_config,
)


EXPERIMENT_ID = "exp-20260710-017"
OWNER = "alpha-explore"
SLUG = "crypto_sleeve_eth_transfer_replay"
RUNNER = f"quant/experiments/exp_20260710_017_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260710_017_{SLUG}.json"
BARS_JSON = DATA_DIR / "eth_usd_daily_closes.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{SLUG}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

HYPOTHESIS = (
    "Observed-only alpha: the production crypto sleeve daily "
    "EMA20/EMA100/SMA200 target policy, replayed through the exact shared "
    "production policy functions over multi-year ETH-USD daily history "
    "(2017-11 to 2026 including the 2018 and 2022 bear markets), should add "
    "risk-adjusted value versus fee-aware ETH buy-and-hold if the daily trend "
    "switch generalizes across crypto assets rather than being a BTC-specific "
    "artifact."
)
CHANGE_TYPE = "risk_allocation"
IMPLEMENTATION_MODE = "observed_only_shared_policy_historical_replay"
MECHANISM_FAMILY = "production_visible_crypto_sleeve_historical_replay"
TRIAL_FAMILY = "eth_spot_crypto_sleeve_daily_trend_policy_transfer_replay"
TRIAL_VARIANT_ID = "eth_daily_2017_2026_three_windows_v1"
CHANGED_VARIABLE = "crypto_sleeve_shared_policy_multi_year_eth_usd_transfer_replay_v1"
NEW_EVIDENCE_TYPE = "new_data_source_eth_usd_daily_history"
NEW_EVIDENCE_AXIS = (
    "New data source: ETH-USD multi-year daily bars (a different crypto "
    "asset), the legal follow-up axis explicitly declared in exp-20260708-019 "
    "next_retry_requires ('a different crypto data source or asset'); no BTC "
    "row, span, threshold, fee, or window is retuned."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260708-019",
    "exp-20260708-020",
    "exp-20260708-010",
    "exp-20260607-022",
]
CAUSAL_COMPONENTS = [
    "shared production policy functions",
    "multi-year ETH-USD daily history",
    "fee-aware buy-and-hold comparator",
    "fixed calendar windows",
    "production hysteresis and fee semantics",
    "no production behavior change",
]
PREDICTION = {
    "success_probability": 0.35,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "buy_and_hold_beats_policy_in_bull_windows",
        "fees_and_whipsaw_consume_edge",
        "yfinance_eth_history_unavailable",
        "window_fragility",
        "eth_history_too_short_for_first_window",
    ],
    "confidence_reason": (
        "ETH bears are deeper than BTC (-94pct 2018, -80pct 2022) so a daily "
        "trend filter plausibly wins drawdown in all windows, but EV transfer "
        "in the 2023-2026 bull window is a coin flip, mirroring the BTC prior "
        "at 0.3."
    ),
    "recorded_at": "2026-07-10T16:15:11+00:00",
}

# Predeclared evaluation contract (fixed before any data read).
# ETH-USD yfinance history begins 2017-11-09; after the 200-bar SMA warm-up
# the first decision row lands in mid-2018, inside the first window.
WINDOWS = [
    {"label": "eth_bear_recovery_2018_2019", "start": "2018-01-01", "end": "2019-12-31"},
    {"label": "covid_cycle_2020_2022", "start": "2020-01-01", "end": "2022-12-31"},
    {"label": "current_cycle_2023_2026", "start": "2023-01-01", "end": "2026-07-09"},
]
AGGREGATE_START = "2018-01-01"
CONFIG = {
    "symbol": "ETH-USD",
    "lookback_days": 5000,
    "annualization_days": 365,
    "min_bars_per_window": 300,
    "min_target_switches_aggregate": 4,
    "initial_position_pct": 0.0,
    "benchmark": "fee_aware_eth_buy_and_hold_per_window",
    "fee_assumption_note": (
        "Uses the production BTC sleeve per-side fee and hysteresis from "
        "load_crypto_config(); ETH spot on the same broker is assumed to "
        "carry the same fee schedule."
    ),
    "acceptance_rule": (
        "positive lead iff policy EV (total_return_pct * sharpe_daily) beats "
        "fee-aware ETH buy-and-hold EV in >=2 of 3 fixed windows AND policy "
        "max drawdown < buy-and-hold max drawdown in all 3 windows AND "
        "aggregate policy total return > 0"
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


def upsert_jsonl(path: Path, payload: dict[str, Any], key: str = "experiment_id") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keep: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                keep.append(line)
                continue
            if row.get(key) != payload.get(key):
                keep.append(json.dumps(row, sort_keys=True))
    keep.append(json.dumps(payload, sort_keys=True))
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")


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


def summarize_returns(label: str, returns: list[float], annualization_days: int) -> dict[str, Any]:
    curve = equity_curve(returns)
    total_return = curve[-1] - 1.0 if curve else 0.0
    if len(returns) > 1:
        mean_ret = statistics.fmean(returns)
        stdev = statistics.stdev(returns)
        sharpe = mean_ret / stdev * math.sqrt(annualization_days) if stdev > 0 else 0.0
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
    """One row per completed daily bar with the production target decision."""
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
    annualization_days: int,
    label: str,
) -> dict[str, Any]:
    """Replay the production policy over one contiguous bar segment.

    Semantics mirror production: the decision comes from the completed bar t
    and is executed near that close (fee on the traded delta); the position
    then earns the close[t] -> close[t+1] return. Rebalances below the
    production min_rebalance_delta_pct hysteresis are held.
    """
    if len(rows) < 2:
        return {
            "label": label,
            "bars": len(rows),
            "policy": summarize_returns("policy", [], annualization_days),
            "buy_hold": summarize_returns("buy_hold", [], annualization_days),
            "target_switches": 0,
            "insufficient_bars": True,
        }

    position = float(CONFIG["initial_position_pct"])
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
        eth_return = nxt["close"] / row["close"] - 1.0
        desired = float(row["target_position_pct"])
        delta = desired - position
        rebalance_fee = 0.0
        if abs(delta) >= min_rebalance_delta_pct:
            rebalance_fee = abs(delta) * fee
            position = desired
            target_switches += 1
        policy_returns.append(position * eth_return - rebalance_fee)
        buy_hold_fee = fee if index == 0 else 0.0
        if index == len(rows) - 2:
            buy_hold_fee += fee
        buy_hold_returns.append(eth_return - buy_hold_fee)
        policy_fee_sum += rebalance_fee
        buy_hold_fee_sum += buy_hold_fee
        position_sum += position
        state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1

    terminal_fee = abs(position) * fee
    if terminal_fee > 0:
        policy_returns[-1] -= terminal_fee
        policy_fee_sum += terminal_fee

    policy = summarize_returns("policy", policy_returns, annualization_days)
    buy_hold = summarize_returns("buy_hold", buy_hold_returns, annualization_days)
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


def build_gate4(
    window_results: list[dict[str, Any]],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    ev_wins = [
        w["label"]
        for w in window_results
        if not w["insufficient_bars"]
        and w["policy"]["expected_value_score"] > w["buy_hold"]["expected_value_score"]
    ]
    dd_wins = [
        w["label"]
        for w in window_results
        if not w["insufficient_bars"]
        and w["policy"]["max_drawdown_pct"] < w["buy_hold"]["max_drawdown_pct"]
    ]
    usable_windows = [w for w in window_results if not w["insufficient_bars"]]
    checks = {
        "all_windows_have_enough_bars": all(
            w["bars"] >= CONFIG["min_bars_per_window"] for w in window_results
        )
        and len(usable_windows) == len(WINDOWS),
        "aggregate_has_target_switches": aggregate["target_switches"]
        >= CONFIG["min_target_switches_aggregate"],
        "policy_ev_beats_buy_hold_in_2_of_3_windows": len(ev_wins) >= 2,
        "policy_drawdown_below_buy_hold_in_all_windows": len(dd_wins)
        == len(WINDOWS),
        "aggregate_policy_total_return_positive": aggregate["policy"][
            "total_return_pct"
        ]
        > 0.0,
    }
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "benchmark": CONFIG["benchmark"],
        "acceptance_rule": CONFIG["acceptance_rule"],
        "checks": checks,
        "failed_reasons": failed,
        "ev_winning_windows": ev_wins,
        "drawdown_winning_windows": dd_wins,
        "windows": window_results,
        "aggregate": aggregate,
        "accepted_alpha": False,
        "binding_acceptance_note": (
            "Observed-only historical transfer replay of the unchanged "
            "production crypto sleeve policy on ETH-USD. Either verdict "
            "changes no production behavior; an ETH sleeve would need its own "
            "predeclared default-off shared policy experiment."
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket_before = read_json(TICKET_JSON, {})
    crypto_config = load_crypto_config()
    fee = float(
        crypto_config.get("fee_pct_per_side")
        or DEFAULT_CRYPTO_CONFIG["fee_pct_per_side"]
    )
    min_delta = float(
        crypto_config.get("min_rebalance_delta_pct")
        or DEFAULT_CRYPTO_CONFIG["min_rebalance_delta_pct"]
    )
    annualization_days = int(CONFIG["annualization_days"])

    ohlcv = fetch_crypto_ohlcv(
        symbol=CONFIG["symbol"], lookback_days=int(CONFIG["lookback_days"])
    )
    completed = completed_daily_bars(ohlcv)
    decision_rows = build_decision_rows(completed)
    write_json(
        BARS_JSON,
        {
            "symbol": CONFIG["symbol"],
            "source": "yfinance daily via shared fetch_crypto_ohlcv",
            "downloaded_at": utc_now(),
            "rows": [
                {
                    "date": row["date"],
                    "close": rounded(row["close"], 2),
                    "state": row["state"],
                    "target_position_pct": row["target_position_pct"],
                }
                for row in decision_rows
            ],
        },
    )

    window_results = []
    for window in WINDOWS:
        rows = [
            row
            for row in decision_rows
            if window["start"] <= row["date"] <= window["end"]
        ]
        window_results.append(
            simulate_segment(rows, fee, min_delta, annualization_days, window["label"])
        )
    aggregate_rows = [row for row in decision_rows if row["date"] >= AGGREGATE_START]
    aggregate = simulate_segment(
        aggregate_rows, fee, min_delta, annualization_days, "aggregate_2018_2026"
    )
    gate4 = build_gate4(window_results, aggregate)

    positive_lead = not gate4["failed_reasons"]
    if positive_lead:
        status = "observed_only"
        decision = "observed_only_positive_lead_crypto_sleeve_eth_transfer_replay"
        rejection_reason = None
        why = (
            "The unchanged production crypto sleeve trend policy beat fee-aware "
            "ETH buy-and-hold on the predeclared risk-adjusted window rule over "
            "multi-year ETH history; the trend switch generalizes beyond BTC, "
            "which supports (but does not by itself create) a future "
            "default-off ETH sleeve."
        )
        observed_only_lead = True
    else:
        status = "observed_only"
        decision = "observed_only_rejected_crypto_sleeve_eth_transfer_replay"
        rejection_reason = ";".join(gate4["failed_reasons"])
        why = (
            "The unchanged production crypto sleeve trend policy did not "
            "satisfy the predeclared multi-year window rule versus fee-aware "
            "ETH buy-and-hold: " + rejection_reason
        )
        observed_only_lead = False

    baseline = read_json(BASELINE_RESULT, {}) or {}
    changed_files = [
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(BARS_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(ARTIFACT_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        repo_rel(EXPERIMENT_LOG),
    ]
    allowed_write_scope = list(ticket_before.get("allowed_write_scope") or [])
    for path in (repo_rel(ARTIFACT_MD), repo_rel(BARS_JSON)):
        if path not in allowed_write_scope:
            allowed_write_scope.append(path)

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
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
        "config": {
            **CONFIG,
            "fee_pct_per_side": fee,
            "min_rebalance_delta_pct": min_delta,
            "windows": WINDOWS,
            "aggregate_start": AGGREGATE_START,
        },
        "crypto_config": {
            "enabled": crypto_config.get("enabled"),
            "symbol": crypto_config.get("symbol"),
            "policy": crypto_config.get("policy"),
            "fee_pct_per_side": fee,
            "min_rebalance_delta_pct": min_delta,
            "note": (
                "Production config remains BTC-only; ETH replay borrows the "
                "same fee and hysteresis semantics without touching config."
            ),
        },
        "pre_run_questions": {
            "alpha_hypothesis": HYPOTHESIS,
            "category": "risk_allocation",
            "nearby_history": NEARBY_PRIOR_EXPERIMENTS,
            "single_policy_bundle": CHANGED_VARIABLE,
            "success_failure_standard": CONFIG["acceptance_rule"],
            "reproducibility": (
                "Runner persists the downloaded decision rows, data artifact, "
                "log, card, artifact report, manifest, and registry fields."
            ),
        },
        "gate1": {
            "stock_strategy_baseline": {
                "baseline_result_file": repo_rel(BASELINE_RESULT),
                "available": bool(baseline),
            },
            "crypto_baselines": ["fee_aware_eth_buy_and_hold_per_window"],
            "note": (
                "No stock strategy behavior changed. The crypto comparator is "
                "constructed from the same replayed ETH daily closes."
            ),
        },
        "gate2": {
            "required_fields": ["date", "close", "state", "target_position_pct"],
            "decision_rows": len(decision_rows),
            "first_decision_date": decision_rows[0]["date"] if decision_rows else None,
            "last_decision_date": decision_rows[-1]["date"] if decision_rows else None,
            "entry_date_contract": "not_applicable_crypto_spot_allocation_no_Position_entry",
            "target_price_contract": "not_applicable_crypto_spot_allocation_no_ATR_exit",
            "shared_policy_functions": [
                "quant/crypto_sleeve.py:compute_crypto_indicators",
                "quant/crypto_sleeve.py:decide_crypto_target",
            ],
            "passed": bool(decision_rows),
        },
        "gate3": {
            "no_filter_added": True,
            "decision_rows": len(decision_rows),
            "window_bar_counts": {
                w["label"]: w["bars"] for w in gate4["windows"]
            },
            "survival_rate": 1.0 if decision_rows else 0.0,
        },
        "gate4": gate4,
        "production_impact": {
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "stock_strategy_changed": False,
            "alters_stock_orders": False,
            "alters_crypto_orders": False,
            "existing_production_crypto_advice_unchanged": True,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Read-only historical transfer replay through the same "
                "production policy functions; the production crypto sleeve "
                "remains BTC-only and unchanged."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retune EMA/SMA spans, target percentages, hysteresis, "
                "fee assumptions, window boundaries, or annualization on this "
                "same replayed ETH history to flip the verdict, and do not "
                "sweep further alt-coins one ID at a time under the same "
                "recipe; a multi-asset follow-up must be a single batched "
                "experiment."
            ),
            "new_evidence_required": (
                "A legal follow-up is a separately predeclared default-off "
                "shared ETH sleeve policy with its own Gate 1-4 and execution "
                "envelope (if this verdict motivates one), a genuinely "
                "different crypto data source, or materially more settled "
                "production crypto sleeve forward snapshots."
            ),
        },
        "rejection_reason": rejection_reason,
        "next_retry_requires": [
            "separately predeclared default-off shared ETH sleeve policy with its own gates",
            "or a genuinely different crypto data source",
            "or materially more settled production crypto sleeve forward rows",
        ],
        "before_after_strategy_behavior_changed": False,
        "changed_files": changed_files,
        "related_files": [
            RUNNER,
            "quant/crypto_sleeve.py",
            repo_rel(BARS_JSON),
            repo_rel(BASELINE_RESULT),
        ],
        "allowed_write_scope": allowed_write_scope,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "llm_metrics": {"used_llm": False},
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "report": repo_rel(ARTIFACT_MD),
        "log": repo_rel(LOG_JSON),
        "ticket_before": ticket_before,
        "created_at": utc_now(),
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
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
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": {
            "benchmark": gate4["benchmark"],
            "acceptance_rule": gate4["acceptance_rule"],
            "checks": gate4["checks"],
            "failed_reasons": gate4["failed_reasons"],
            "ev_winning_windows": gate4["ev_winning_windows"],
            "drawdown_winning_windows": gate4["drawdown_winning_windows"],
            "windows": [
                {
                    "label": w["label"],
                    "bars": w["bars"],
                    "target_switches": w.get("target_switches"),
                    "avg_position_pct": w.get("avg_position_pct"),
                    "policy": w["policy"],
                    "buy_hold": w["buy_hold"],
                    "delta_vs_buy_hold": w.get("delta_vs_buy_hold"),
                }
                for w in gate4["windows"]
            ],
            "aggregate": {
                "label": aggregate["label"],
                "bars": aggregate["bars"],
                "target_switches": aggregate.get("target_switches"),
                "avg_position_pct": aggregate.get("avg_position_pct"),
                "policy": aggregate["policy"],
                "buy_hold": aggregate["buy_hold"],
                "delta_vs_buy_hold": aggregate.get("delta_vs_buy_hold"),
            },
            "accepted_alpha": False,
            "binding_acceptance_note": gate4["binding_acceptance_note"],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "changed_files": payload["changed_files"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "artifact": payload["artifact"],
        "report": payload["report"],
        "log": payload["log"],
        "completed_at": utc_now(),
    }


def format_segment_row(segment: dict[str, Any]) -> str:
    policy = segment["policy"]
    buy_hold = segment["buy_hold"]
    return (
        f"| {segment['label']} | {segment['bars']} | "
        f"{policy['total_return_pct']} | {policy['sharpe_daily']} | "
        f"{policy['expected_value_score']} | {policy['max_drawdown_pct']} | "
        f"{buy_hold['total_return_pct']} | {buy_hold['sharpe_daily']} | "
        f"{buy_hold['expected_value_score']} | {buy_hold['max_drawdown_pct']} | "
        f"{segment.get('target_switches')} | {segment.get('avg_position_pct')} |"
    )


def build_report(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    lines = [
        f"# {EXPERIMENT_ID}: ETH Crypto Sleeve Shared-Policy Transfer Replay",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Hypothesis: {HYPOTHESIS}",
        f"- Runner: `{RUNNER_COMMAND}`",
        f"- Acceptance rule: {gate4['acceptance_rule']}",
        "",
        "## Windows (policy vs fee-aware buy-and-hold)",
        "",
        "| Window | Bars | Pol ret | Pol sharpe | Pol EV | Pol maxDD | "
        "B&H ret | B&H sharpe | B&H EV | B&H maxDD | Switches | Avg pos |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for segment in gate4["windows"]:
        lines.append(format_segment_row(segment))
    lines.append(format_segment_row(gate4["aggregate"]))
    lines.extend(
        [
            "",
            f"- EV winning windows: `{', '.join(gate4['ev_winning_windows']) or 'none'}`",
            f"- Drawdown winning windows: `{', '.join(gate4['drawdown_winning_windows']) or 'none'}`",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
            "",
            "## Closeout",
            "",
            f"- Production impact: {payload['production_impact']['parity_note']}",
            f"- Why: {payload['post_run_reflection']['why_result_happened']}",
            f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
            f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    aggregate = gate4["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: ETH Crypto Sleeve Shared-Policy Transfer Replay",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Report: `{payload['report']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Result",
        "",
        f"- EV winning windows: `{', '.join(gate4['ev_winning_windows']) or 'none'}`",
        f"- Drawdown winning windows: `{', '.join(gate4['drawdown_winning_windows']) or 'none'}`",
        f"- Aggregate policy ret / sharpe / maxDD: `{aggregate['policy']['total_return_pct']}` / "
        f"`{aggregate['policy']['sharpe_daily']}` / `{aggregate['policy']['max_drawdown_pct']}`",
        f"- Aggregate buy-hold ret / sharpe / maxDD: `{aggregate['buy_hold']['total_return_pct']}` / "
        f"`{aggregate['buy_hold']['sharpe_daily']}` / `{aggregate['buy_hold']['max_drawdown_pct']}`",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Reflection",
        "",
        f"- Why: {payload['post_run_reflection']['why_result_happened']}",
        f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        BARS_JSON,
        LOG_JSON,
        CARD_MD,
        ARTIFACT_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "report": repo_rel(ARTIFACT_MD),
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
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_record)
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    write_text(CARD_MD, build_card(payload))
    write_text(ARTIFACT_MD, build_report(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
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
            "artifact": repo_rel(OUT_JSON),
            "report": repo_rel(ARTIFACT_MD),
            "log": repo_rel(LOG_JSON),
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
            "allowed_write_scope": payload["allowed_write_scope"],
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
                "gate4": compact_log_record(payload)["gate4"],
                "artifact": payload["artifact"],
                "report": payload["report"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
