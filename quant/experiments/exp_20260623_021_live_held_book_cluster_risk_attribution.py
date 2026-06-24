"""exp-20260623-021: live held-book AI/semis cluster risk attribution.

Observed-only alpha-search attribution. This runner asks whether the current
live held book has enough AI/semis covariance concentration to justify a later
shared risk-allocation Gate 1-4 experiment. It changes no strategy, helper,
adapter, ranking, sizing, exit, paper ledger, live ledger, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-021"
SLUG = "live_held_book_cluster_risk_attribution"
RUNNER = f"quant/experiments/exp_20260623_021_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
OWNER = "alpha-explore"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_021_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OPEN_POSITIONS = REPO_ROOT / "operator_inputs" / "open_positions.json"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

HYPOTHESIS = (
    "risk_allocation: current live held-book AI/semis concentration may dominate "
    "portfolio variance; if a capped cluster envelope materially lowers ex-ante "
    "volatility without destroying trailing risk-adjusted return, it justifies a "
    "later Gate 1-4 shared risk-allocation experiment rather than more "
    "candidate-pool scans."
)
CHANGE_TYPE = "risk_allocation_observed_only"
MECHANISM_FAMILY = "live_held_book_risk_allocation_attribution"
TRIAL_FAMILY = "live_held_book_cluster_concentration_attribution"
TRIAL_VARIANT_ID = "ai_semis_cluster_cap_observed_only_v1"
CHANGED_VARIABLE = "live_held_book_ai_semis_cluster_risk_attribution_v1"
NEW_EVIDENCE_TYPE = "current_live_position_risk_surface"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260623-019", "exp-20260623-020"]
CAUSAL_COMPONENTS = [
    "current open-position weights",
    "broad warehouse return covariance",
    "cluster-cap counterfactual",
    "observed-only verdict",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260623-021",
    "experiments/logs/exp-20260623-021.json",
    "experiments/cards/exp-20260623-021.md",
    "experiments/manifests/exp-20260623-021.json",
    "experiments/tickets/exp-20260623-021.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

DEFAULT_PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "lookback_return_bias",
        "no_canonical_gate4_evidence",
        "cluster_cap_sacrifices_return",
        "no_material_vol_reduction",
    ],
    "confidence_reason": (
        "This uses a genuinely current live-position risk surface rather than "
        "another frozen-window candidate scan. The possible money mechanism is "
        "risk allocation: portfolio variance may be dominated by correlated "
        "AI/semis names. Main disconfirmers are winner-lookback return bias and "
        "the fact that observed-only covariance cannot justify live cap changes "
        "without a later shared Gate 1-4 policy."
    ),
    "recorded_at": "2026-06-23T17:05:19+00:00",
}

AI_SEMIS_CLUSTER = {"AMD", "COHR", "CRDO", "MRVL", "NBIS", "NVDA"}
ACCOUNT_POSITION_GROUPS = (
    "core_positions",
    "positions",
    "observations",
    "sleeve_positions",
    "legacy_positions",
)
TRADING_DAYS = 252
MIN_HISTORY_DAYS = 60
CLUSTER_CAP = 0.30
MATERIAL_CLUSTER_RISK_SHARE = 0.45
MATERIAL_VOL_REDUCTION_PP = 5.0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_float(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if isinstance(value, list):
        return [clean_float(v) for v in value]
    if isinstance(value, dict):
        return {k: clean_float(v) for k, v in value.items()}
    return value


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                rows.append({"_raw_unparseable": line})
                continue
            if existing.get("experiment_id") != row["experiment_id"]:
                rows.append(existing)
    rows.append(row)
    path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n",
        encoding="utf-8",
    )


def baseline_metrics() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT)
    windows = data.get("windows") or []
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "aggregate_expected_value_score": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "aggregate_total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "total_trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "aggregate_signals_generated": sum(int(w.get("signals_generated") or 0) for w in windows),
        "aggregate_signals_survived": sum(int(w.get("signals_survived") or 0) for w in windows),
        "min_survival_rate": min(float(w.get("survival_rate") or 0.0) for w in windows),
        "max_window_drawdown_pct": max(float(w.get("max_drawdown_pct") or 0.0) for w in windows),
        "windows": windows,
    }


def load_positions() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = read_json(OPEN_POSITIONS)
    out: list[dict[str, Any]] = []
    for group in ACCOUNT_POSITION_GROUPS:
        for row in payload.get(group) or []:
            if str(row.get("direction", "long")).lower() != "long":
                continue
            market_val = row.get("market_val")
            if not isinstance(market_val, (int, float)) or market_val <= 0:
                continue
            copy = dict(row)
            copy["position_group"] = group
            out.append(copy)
    return payload, out


def load_closes(tickers: list[str]) -> dict[str, dict[str, float]]:
    con = sqlite3.connect(WAREHOUSE)
    try:
        out: dict[str, dict[str, float]] = {}
        for ticker in tickers:
            rows = con.execute(
                """
                SELECT date, close
                FROM ohlcv
                WHERE ticker = ? AND close IS NOT NULL
                ORDER BY date
                """,
                (ticker,),
            ).fetchall()
            if rows:
                out[ticker] = {str(day): float(close) for day, close in rows}
        return out
    finally:
        con.close()


def daily_log_returns(closes: dict[str, float], dates: list[str]) -> np.ndarray:
    px = np.array([closes[day] for day in dates], dtype=float)
    return np.diff(np.log(px))


def summarize_risk() -> dict[str, Any]:
    account, positions = load_positions()
    tickers = sorted({str(p["ticker"]).upper() for p in positions})
    closes = load_closes(tickers + ["SPY"])

    eligible = [
        ticker
        for ticker in tickers
        if ticker in closes and len(closes[ticker]) >= MIN_HISTORY_DAYS + 1
    ]
    dropped = [
        {
            "ticker": ticker,
            "reason": "missing_or_short_warehouse_history",
            "history_rows": len(closes.get(ticker, {})),
        }
        for ticker in tickers
        if ticker not in eligible
    ]
    if "SPY" not in closes or len(closes["SPY"]) < MIN_HISTORY_DAYS + 1:
        raise RuntimeError("SPY warehouse history is required for beta attribution")

    common_dates = set(closes["SPY"])
    for ticker in eligible:
        common_dates &= set(closes[ticker])
    dates = sorted(common_dates)
    if len(dates) < MIN_HISTORY_DAYS + 1:
        raise RuntimeError(f"not enough common history: {len(dates)} dates")

    return_dates = dates[1:]
    returns = np.column_stack([daily_log_returns(closes[ticker], dates) for ticker in eligible])
    spy_returns = daily_log_returns(closes["SPY"], dates)

    market_vals: dict[str, float] = {}
    field_coverage = {
        "entry_date_present": 0,
        "target_price_present": 0,
        "market_val_present": 0,
        "position_count": len(positions),
    }
    position_rows = []
    for row in positions:
        ticker = str(row["ticker"]).upper()
        market_val = float(row["market_val"])
        market_vals[ticker] = market_vals.get(ticker, 0.0) + market_val
        if row.get("entry_date"):
            field_coverage["entry_date_present"] += 1
        if isinstance(row.get("target_price"), (int, float)):
            field_coverage["target_price_present"] += 1
        if isinstance(row.get("market_val"), (int, float)):
            field_coverage["market_val_present"] += 1
        position_rows.append(
            {
                "ticker": ticker,
                "group": row.get("position_group"),
                "sleeve": row.get("sleeve"),
                "slot_policy": row.get("slot_policy"),
                "market_val": market_val,
                "entry_date": row.get("entry_date"),
                "target_price_present": isinstance(row.get("target_price"), (int, float)),
            }
        )

    invested_total = sum(market_vals[ticker] for ticker in eligible)
    account_value = float(account.get("portfolio_value_usd") or 0.0)
    cash_usd = float(account.get("cash_usd") or 0.0)
    if invested_total <= 0:
        raise RuntimeError("no eligible invested positions")

    weights = np.array([market_vals[ticker] for ticker in eligible], dtype=float)
    weights = weights / weights.sum()

    cov = np.cov(returns, rowvar=False) * TRADING_DAYS
    if cov.ndim == 0:
        cov = np.array([[float(cov)]])
    port_var = float(weights @ cov @ weights)
    port_vol = math.sqrt(max(port_var, 0.0))
    marginal = cov @ weights
    component = weights * marginal
    risk_share = component / port_var if port_var > 0 else np.zeros_like(weights)
    corr = np.corrcoef(returns, rowvar=False)
    if corr.ndim == 0:
        corr = np.array([[1.0]])
    ann_return = returns.mean(axis=0) * TRADING_DAYS
    port_return = float(weights @ ann_return)
    port_sharpe = port_return / port_vol if port_vol else None

    spy_var = float(np.var(spy_returns, ddof=1))
    idx = {ticker: i for i, ticker in enumerate(eligible)}
    cluster_tickers = [ticker for ticker in eligible if ticker in AI_SEMIS_CLUSTER]
    cluster_idx = [idx[ticker] for ticker in cluster_tickers]
    non_cluster_idx = [i for i, ticker in enumerate(eligible) if ticker not in AI_SEMIS_CLUSTER]

    if cluster_idx:
        cluster_weight = float(weights[cluster_idx].sum())
        cluster_market_val = sum(market_vals[ticker] for ticker in cluster_tickers)
        cluster_risk_share = float(risk_share[cluster_idx].sum())
    else:
        cluster_weight = 0.0
        cluster_market_val = 0.0
        cluster_risk_share = 0.0

    if len(cluster_idx) > 1:
        sub_corr = corr[np.ix_(cluster_idx, cluster_idx)]
        cluster_intra_corr = float(
            (sub_corr.sum() - len(cluster_idx)) / (len(cluster_idx) * (len(cluster_idx) - 1))
        )
    else:
        cluster_intra_corr = None

    per_ticker = []
    for ticker in eligible:
        i = idx[ticker]
        beta_spy = None
        if spy_var > 0:
            beta_spy = float(np.cov(returns[:, i], spy_returns, ddof=1)[0, 1] / spy_var)
        per_ticker.append(
            {
                "ticker": ticker,
                "market_val": market_vals[ticker],
                "account_weight": market_vals[ticker] / account_value if account_value else None,
                "equity_book_weight": float(weights[i]),
                "risk_share": float(risk_share[i]),
                "annualized_vol": math.sqrt(max(float(cov[i, i]), 0.0)),
                "trailing_annualized_return_proxy": float(ann_return[i]),
                "beta_spy": beta_spy,
                "cluster_member": ticker in AI_SEMIS_CLUSTER,
            }
        )
    per_ticker.sort(key=lambda row: row["risk_share"], reverse=True)

    adjacent_correlations = []
    if cluster_idx:
        for ticker in eligible:
            if ticker in AI_SEMIS_CLUSTER:
                continue
            i = idx[ticker]
            adjacent_correlations.append(
                {
                    "ticker": ticker,
                    "avg_corr_to_cluster": float(np.mean([corr[i, j] for j in cluster_idx])),
                    "equity_book_weight": float(weights[i]),
                    "risk_share": float(risk_share[i]),
                }
            )
        adjacent_correlations.sort(key=lambda row: row["avg_corr_to_cluster"], reverse=True)

    cap_counterfactual = None
    if cluster_idx and cluster_weight > CLUSTER_CAP and non_cluster_idx:
        capped = weights.copy()
        scale = CLUSTER_CAP / cluster_weight
        for i in cluster_idx:
            capped[i] = weights[i] * scale
        excess = cluster_weight - CLUSTER_CAP
        non_weight = float(weights[non_cluster_idx].sum())
        for i in non_cluster_idx:
            capped[i] = weights[i] + excess * (weights[i] / non_weight)
        capped_vol = math.sqrt(max(float(capped @ cov @ capped), 0.0))
        capped_return = float(capped @ ann_return)
        capped_sharpe = capped_return / capped_vol if capped_vol else None

        cash_weights = weights.copy()
        for i in cluster_idx:
            cash_weights[i] = weights[i] * scale
        cash_weight = 1.0 - float(cash_weights.sum())
        cash_vol = math.sqrt(max(float(cash_weights @ cov @ cash_weights), 0.0))
        cash_return = float(cash_weights @ ann_return)
        cash_sharpe = cash_return / cash_vol if cash_vol else None

        cap_counterfactual = {
            "cluster_cap_equity_book_weight": CLUSTER_CAP,
            "redeploy_excess_pro_rata_non_cluster": {
                "annualized_vol_before": port_vol,
                "annualized_vol_after": capped_vol,
                "annualized_vol_delta_pp": (capped_vol - port_vol) * 100.0,
                "trailing_annualized_return_proxy_before": port_return,
                "trailing_annualized_return_proxy_after": capped_return,
                "trailing_annualized_return_proxy_delta_pp": (capped_return - port_return) * 100.0,
                "trailing_sharpe_proxy_before": port_sharpe,
                "trailing_sharpe_proxy_after": capped_sharpe,
            },
            "redeploy_excess_to_cash": {
                "annualized_vol_before": port_vol,
                "annualized_vol_after": cash_vol,
                "annualized_vol_delta_pp": (cash_vol - port_vol) * 100.0,
                "trailing_annualized_return_proxy_before": port_return,
                "trailing_annualized_return_proxy_after": cash_return,
                "trailing_annualized_return_proxy_delta_pp": (cash_return - port_return) * 100.0,
                "trailing_sharpe_proxy_before": port_sharpe,
                "trailing_sharpe_proxy_after": cash_sharpe,
                "cash_weight_created": cash_weight,
            },
        }

    material_vol_reduction = False
    vol_reduction_pp = None
    if cap_counterfactual:
        vol_reduction_pp = -cap_counterfactual["redeploy_excess_to_cash"]["annualized_vol_delta_pp"]
        material_vol_reduction = vol_reduction_pp >= MATERIAL_VOL_REDUCTION_PP

    observed_lead = cluster_risk_share >= MATERIAL_CLUSTER_RISK_SHARE and material_vol_reduction
    return {
        "as_of": account.get("as_of"),
        "account": {
            "account": account.get("account"),
            "portfolio_value_usd": account_value,
            "cash_usd": cash_usd,
            "cash_weight": cash_usd / account_value if account_value else None,
            "invested_market_value_priced": invested_total,
            "priced_position_count": len(eligible),
            "all_position_count": len(positions),
        },
        "input_paths": {
            "open_positions": repo_rel(OPEN_POSITIONS),
            "warehouse": repo_rel(WAREHOUSE),
        },
        "field_coverage": field_coverage,
        "position_rows": position_rows,
        "priced_tickers": eligible,
        "dropped_tickers": dropped,
        "common_history": {
            "start": dates[0],
            "end": dates[-1],
            "price_dates": len(dates),
            "return_dates": len(return_dates),
            "min_history_days": MIN_HISTORY_DAYS,
        },
        "portfolio_risk": {
            "annualized_vol": port_vol,
            "trailing_annualized_return_proxy": port_return,
            "trailing_sharpe_proxy": port_sharpe,
            "risk_model": "annualized covariance of daily log returns over common warehouse history",
            "return_proxy_caveat": "Trailing realized return is biased by live winner selection; use vol/correlation/risk-share as the robust diagnostic.",
        },
        "ai_semis_cluster": {
            "predeclared_tickers": sorted(AI_SEMIS_CLUSTER),
            "present_tickers": sorted(cluster_tickers),
            "market_value_usd": cluster_market_val,
            "account_weight": cluster_market_val / account_value if account_value else None,
            "equity_book_weight": cluster_weight,
            "risk_share": cluster_risk_share,
            "avg_intra_cluster_corr": cluster_intra_corr,
            "risk_share_threshold": MATERIAL_CLUSTER_RISK_SHARE,
            "material_risk_concentration": cluster_risk_share >= MATERIAL_CLUSTER_RISK_SHARE,
        },
        "adjacent_non_cluster_corr_to_ai_semis": adjacent_correlations[:10],
        "per_ticker_risk": per_ticker,
        "cluster_cap_counterfactual": cap_counterfactual,
        "observed_only_lead": observed_lead,
        "observed_only_lead_basis": {
            "cluster_risk_share": cluster_risk_share,
            "required_cluster_risk_share": MATERIAL_CLUSTER_RISK_SHARE,
            "cash_redeploy_vol_reduction_pp": vol_reduction_pp,
            "required_vol_reduction_pp": MATERIAL_VOL_REDUCTION_PP,
        },
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    before = baseline_metrics()
    risk = summarize_risk()
    observed_lead = bool(risk["observed_only_lead"])

    failed_reasons = ["observed_only_current_book_not_canonical_gate4"]
    if observed_lead:
        failed_reasons.append("requires_later_shared_policy_gate4_before_any_cap_change")
        decision = "observed_only_cluster_risk_concentration_lead_not_promoted"
        status = "observed_only"
    else:
        if not risk["ai_semis_cluster"]["material_risk_concentration"]:
            failed_reasons.append("cluster_risk_share_not_material")
        if not risk["observed_only_lead_basis"]["cash_redeploy_vol_reduction_pp"]:
            failed_reasons.append("no_cap_counterfactual_available")
        elif (
            risk["observed_only_lead_basis"]["cash_redeploy_vol_reduction_pp"]
            < MATERIAL_VOL_REDUCTION_PP
        ):
            failed_reasons.append("cluster_cap_vol_reduction_not_material")
        decision = "rejected_no_promotable_live_cluster_cap_edge"
        status = "rejected"

    after = dict(before)
    delta = {
        "aggregate_expected_value_score": 0.0,
        "aggregate_total_pnl": 0.0,
        "total_trade_count": 0,
        "strategy_behavior_changed": False,
        "observed_only_lead": observed_lead,
        "cluster_risk_share": risk["ai_semis_cluster"]["risk_share"],
        "cash_redeploy_vol_reduction_pp": risk["observed_only_lead_basis"][
            "cash_redeploy_vol_reduction_pp"
        ],
    }

    calibration = {
        "actual_decision": decision,
        "actual_success": 0,
        "brier_score": round(DEFAULT_PREDICTION["success_probability"] ** 2, 4),
        "predicted_success_probability": DEFAULT_PREDICTION["success_probability"],
        "predicted_failure_modes": DEFAULT_PREDICTION["main_failure_modes"],
        "failure_modes_observed": failed_reasons,
        "predicted_failure_mode_hit": any(
            mode in failed_reasons
            for mode in (
                "no_canonical_gate4_evidence",
                "no_material_vol_reduction",
                "cluster_cap_sacrifices_return",
                "lookback_return_bias",
            )
        ),
        "surprise_note": (
            "The concentration surface can be diagnostic, but it is still not "
            "canonical strategy evidence because it is current-book, "
            "lookback-biased, and not a shared Gate 1-4 policy."
        ),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_summary": (
            "Observed-only current held-book AI/semis covariance concentration "
            "and 30% cluster-cap counterfactual; no strategy behavior changed."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "prior_trial_count": 0,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": DEFAULT_PREDICTION,
        "calibration": calibration,
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "gate1": {"passed": True, "baseline_loaded": True, "baseline_metrics": before},
        "gate2": {
            "passed": True,
            "runtime_fields_checked": [
                "entry_date",
                "target_price",
                "market_val",
                "portfolio_value_usd",
                "warehouse close history",
            ],
            "field_coverage": risk["field_coverage"],
            "priced_position_count": risk["account"]["priced_position_count"],
            "dropped_tickers": risk["dropped_tickers"],
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "baseline_min_survival_rate": before["min_survival_rate"],
            "note": "No entry filter, ranking, sizing, exit, or candidate generation rule changed.",
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "observed_only": True,
            "strategy_rerun_required": False,
            "acceptance_rule": {
                "material_cluster_risk_share": MATERIAL_CLUSTER_RISK_SHARE,
                "material_cash_redeploy_vol_reduction_pp": MATERIAL_VOL_REDUCTION_PP,
                "canonical_gate4_required_before_cap_change": True,
            },
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "risk_attribution": risk["observed_only_lead_basis"],
        },
        "risk_attribution": risk,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "parity_note": (
                "Read-only current-book risk attribution. Any real cluster cap "
                "requires a separate shared policy and canonical Gate 1-4 test."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The current book risk surface is useful for risk attribution, "
                "but it cannot be accepted alpha because it is not a historical "
                "PIT policy replay and does not change before/after strategy "
                "metrics."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not directly cap AI/semis, tune the cap percentage, or "
                "reclassify adjacent tickers from this current-book snapshot "
                "alone."
            ),
            "new_evidence_required": (
                "A retry needs a shared risk-allocation policy with canonical "
                "Gate 1-4 before/after windows, or forward/live risk outcomes "
                "under a predeclared cluster envelope."
            ),
            "outcome_summary": (
                f"AI/semis risk share {risk['ai_semis_cluster']['risk_share']:.2%}; "
                f"observed-only lead={observed_lead}; no strategy behavior changed."
            ),
        },
        "rejection_reason": (
            "Observed-only current-book covariance attribution is not canonical "
            "Gate 4 evidence and cannot promote a live risk cap."
        ),
        "next_retry_requires": [
            "shared risk-allocation policy",
            "canonical Gate 1-4 before/after replay",
            "forward/live outcomes under a fixed cluster envelope",
        ],
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(OPEN_POSITIONS),
            repo_rel(WAREHOUSE),
        ],
        "reproduction_command": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
    }
    return clean_float(payload)


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "baseline_result_file",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "related_files",
        "reproduction_command",
        "anti_js",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = repo_rel(OUT_JSON)
    record["log"] = repo_rel(LOG_JSON)
    return record


def build_card(payload: dict[str, Any]) -> str:
    risk = payload["risk_attribution"]
    cluster = risk["ai_semis_cluster"]
    cap = risk["cluster_cap_counterfactual"] or {}
    cash_cf = cap.get("redeploy_excess_to_cash") or {}
    lines = [
        f"# {EXPERIMENT_ID}: Live Held-Book Cluster Risk Attribution",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Observed-only lead: `{payload['observed_only_lead']}`",
        f"- Hypothesis: {payload['hypothesis']}",
        "",
        "## Result",
        "",
        f"- AI/semis present tickers: `{', '.join(cluster['present_tickers'])}`",
        f"- Account weight: `{cluster['account_weight']:.2%}`",
        f"- Equity-book weight: `{cluster['equity_book_weight']:.2%}`",
        f"- Risk share: `{cluster['risk_share']:.2%}`",
        f"- Average intra-cluster correlation: `{cluster['avg_intra_cluster_corr']}`",
        f"- Cash-redeploy cap vol delta: `{cash_cf.get('annualized_vol_delta_pp')}` pp",
        "",
        "## Decision",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Production Impact",
        "",
        "No strategy, ranking, sizing, exit, order, paper ledger, or live ledger behavior changed.",
        "",
        "## Reproduce",
        "",
        f"```powershell\n{RUNNER_COMMAND}\n```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
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
            repo_rel(path if path.is_absolute() else REPO_ROOT / path): {
                "exists": (path if path.is_absolute() else REPO_ROOT / path).exists(),
                "sha256": sha256(path if path.is_absolute() else REPO_ROOT / path),
            }
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    risk = payload["risk_attribution"]
    risk_summary = {
        "observed_only_lead": payload["observed_only_lead"],
        "ai_semis_cluster": risk["ai_semis_cluster"],
        "lead_basis": risk["observed_only_lead_basis"],
        "common_history": risk["common_history"],
        "top_risk_tickers": risk["per_ticker_risk"][:5],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "risk_attribution_summary": risk_summary,
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    cluster = payload["risk_attribution"]["ai_semis_cluster"]
    lead_basis = payload["risk_attribution"]["observed_only_lead_basis"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "cluster_account_weight": cluster["account_weight"],
                "cluster_equity_book_weight": cluster["equity_book_weight"],
                "cluster_risk_share": cluster["risk_share"],
                "cash_redeploy_vol_reduction_pp": lead_basis[
                    "cash_redeploy_vol_reduction_pp"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
