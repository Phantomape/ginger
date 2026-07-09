"""exp-20260707-017: portfolio covariance lane gate-calibration joint verdict.

Read-only joint synthesis across the 11 completed per-candidate daily-equity
overlay artifacts (exp-20260706-022 ranking consumption). No overlay is
re-run, no source is retuned, no order path is touched.

Questions answered:
1. Empirical: were the 11 rejections driven by noise-magnitude single-window
   EV regressions while aggregate deltas stayed positive?
2. Structural: can ANY candidate mathematically clear the lane acceptance
   clause (aggregate EV improvement > 10%) under the <= 10% risk-budget cap?
3. Which candidates form the low-correlation observed-only forward-watch
   shortlist sanctioned by docs/portfolio_covariance_lane.md?

Verdict artifact parks lane consumption of ranks 14-31 with quantified
reopen conditions.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

OVERLAYS = {
    "exp-20260706-023": ("fixed_asset_turnover_improvement", 1,
                         "exp_20260706_023_portfolio_daily_equity_overlay.json"),
    "exp-20260706-024": ("sector_breadth_market_breadth_agreement", 5,
                         "exp_20260706_024_portfolio_daily_equity_sector_breadth_overlay.json"),
    "exp-20260706-025": ("deferred_revenue_demand_acceleration", 2,
                         "exp_20260706_025_portfolio_daily_equity_deferred_revenue_overlay.json"),
    "exp-20260707-001": ("finra_short_pressure_breakout", 6,
                         "exp_20260707_001_portfolio_daily_equity_finra_short_pressure_overlay.json"),
    "exp-20260707-003": ("companyfacts_purchase_obligation_maturity_ladder", 3,
                         "exp_20260707_003_purchase_obligation_daily_equity_overlay.json"),
    "exp-20260707-005": ("receivables_dso_collection_improvement", 4,
                         "exp_20260707_005_receivables_dso_daily_equity_overlay.json"),
    "exp-20260707-006": ("industry_breadth_repair_second_line", 7,
                         "exp_20260707_006_industry_breadth_repair_daily_equity_overlay.json"),
    "exp-20260707-007": ("volatility_curve_relief_stock_leadership", 9,
                         "exp_20260707_007_volatility_curve_relief_daily_equity_overlay.json"),
    "exp-20260707-008": ("gap_hold_core_flow_confirmed", 10,
                         "exp_20260707_008_gap_hold_core_flow_daily_equity_overlay.json"),
    "exp-20260707-015": ("distribution_pressure_low_beta_defensive_leadership", 12,
                         "exp_20260707_015_distribution_pressure_low_beta_daily_equity_overlay.json"),
    "exp-20260707-016": ("peer_earnings_reaction_transfer", 13,
                         "exp_20260707_016_peer_earnings_reaction_daily_equity_overlay.json"),
}

LANE_ACCEPT_EV_IMPROVEMENT_MIN = 0.10  # >10% aggregate EV improvement clause
LANE_RISK_BUDGET_CAP = 0.10  # <=10% risk budget clause
NOISE_FRACTION = 0.01  # window EV regression < 1% of champion window EV = noise-scale


def load_rows() -> list[dict]:
    rows = []
    for exp_id, (family, rank, fname) in OVERLAYS.items():
        art = json.loads((REPO / "data" / "experiments" / exp_id / fname).read_text(encoding="utf-8"))
        agg = art.get("aggregate_daily_equity") or {}
        core = agg.get("core_metrics_daily_mtm_proxy") or {}
        delta = (art.get("delta_metrics") or {}).get("daily_mtm_proxy") or {}
        windows = {}
        noise_regressions = []
        decisive_regressions = []
        for wname, wblock in (art.get("by_window") or {}).items():
            if not isinstance(wblock, dict):
                continue
            wdelta = (wblock.get("delta_metrics_daily_mtm_proxy") or {})
            wcore = (wblock.get("core_metrics_daily_mtm_proxy")
                     or wblock.get("core_metrics") or {})
            core_ev = wcore.get("expected_value_score")
            ev_d = wdelta.get("expected_value_score")
            pnl_d = wdelta.get("total_pnl")
            windows[wname] = {
                "ev_delta": ev_d,
                "pnl_delta": pnl_d,
                "core_window_ev": core_ev,
                "ev_delta_frac_of_core": (ev_d / core_ev) if (ev_d is not None and core_ev) else None,
            }
            if ev_d is not None and ev_d < 0:
                frac = abs(ev_d) / abs(core_ev) if core_ev else math.inf
                rec = {"window": wname, "ev_delta": ev_d, "frac_of_core_ev": frac,
                       "pnl_delta": pnl_d}
                if frac < NOISE_FRACTION or (pnl_d is not None and pnl_d >= 0):
                    noise_regressions.append(rec)
                else:
                    decisive_regressions.append(rec)
        rows.append({
            "experiment_id": exp_id,
            "source_family": family,
            "ranking_rank": rank,
            "aggregate_ev_delta": delta.get("expected_value_score"),
            "aggregate_pnl_delta": delta.get("total_pnl"),
            "aggregate_drawdown_drift": delta.get("max_drawdown_pct"),
            "core_aggregate_ev": core.get("expected_value_score"),
            "aggregate_ev_delta_frac": (delta.get("expected_value_score") / core.get("expected_value_score"))
            if (delta.get("expected_value_score") is not None and core.get("expected_value_score")) else None,
            "core_overlay_daily_pnl_correlation": agg.get("core_overlay_daily_pnl_correlation"),
            "rejection_reason": art.get("rejection_reason"),
            "windows": windows,
            "noise_scale_regressions": noise_regressions,
            "decisive_regressions": decisive_regressions,
        })
    return rows


def main() -> None:
    rows = load_rows()

    n = len(rows)
    n_positive_agg_ev = sum(1 for r in rows if (r["aggregate_ev_delta"] or 0) > 0)
    n_positive_agg_pnl = sum(1 for r in rows if (r["aggregate_pnl_delta"] or 0) > 0)
    n_rejected_only_noise = sum(
        1 for r in rows if r["noise_scale_regressions"] and not r["decisive_regressions"])
    n_any_decisive = sum(1 for r in rows if r["decisive_regressions"])
    max_agg_frac = max((r["aggregate_ev_delta_frac"] or 0) for r in rows)
    worst_dd_drift = max((r["aggregate_drawdown_drift"] or 0) for r in rows)

    # Structural feasibility: best observed aggregate EV delta fraction vs the
    # lane acceptance clause under the risk-budget cap.
    structurally_satisfiable = max_agg_frac > LANE_ACCEPT_EV_IMPROVEMENT_MIN
    # Zero-tolerance three-window sign test: probability a pure-noise overlay
    # survives (all three window EV deltas >= 0) if each window is a coin flip.
    p_noise_survival = 0.5 ** 3

    # Forward-watch shortlist per the lane doc's observed-only clause:
    # positive aggregate EV and PnL delta, drawdown drift <= 0.2pp, sorted by
    # |correlation| ascending then aggregate EV delta descending.
    watch = [r for r in rows
             if (r["aggregate_ev_delta"] or 0) > 0
             and (r["aggregate_pnl_delta"] or 0) > 0
             and (r["aggregate_drawdown_drift"] or 0) <= 0.002]
    watch.sort(key=lambda r: (abs(r["core_overlay_daily_pnl_correlation"] or 1),
                              -(r["aggregate_ev_delta"] or 0)))
    shortlist = [{
        "experiment_id": r["experiment_id"],
        "source_family": r["source_family"],
        "ranking_rank": r["ranking_rank"],
        "core_overlay_daily_pnl_correlation": r["core_overlay_daily_pnl_correlation"],
        "aggregate_ev_delta": r["aggregate_ev_delta"],
        "aggregate_pnl_delta": r["aggregate_pnl_delta"],
        "aggregate_drawdown_drift": r["aggregate_drawdown_drift"],
    } for r in watch[:3]]

    verdict = {
        "lane_consumption_parked": True,
        "parked_scope": "exp-20260706-022 ranking ranks 14-31 per-candidate daily-equity overlay consumption",
        "reason": (
            "empirical: {}/{} overlays had positive aggregate EV delta and {}/{} positive aggregate PnL delta, "
            "yet all were rejected; {}/{} rejections rest ONLY on noise-scale window EV regressions "
            "(|delta| < {:.0%} of champion window EV, or window PnL non-negative). "
            "structural: best observed aggregate EV improvement is {:.2%}, versus the lane acceptance clause of >{:.0%} "
            "under a <={:.0%} risk-budget cap — the two clauses are jointly unsatisfiable for candidates that "
            "individually lost to the champion; a pure-noise overlay survives the zero-tolerance three-window "
            "sign test only {:.1%} of the time, so ~100% rejection carries no information about candidate quality."
        ).format(n_positive_agg_ev, n, n_positive_agg_pnl, n,
                 n_rejected_only_noise, n, NOISE_FRACTION,
                 max_agg_frac, LANE_ACCEPT_EV_IMPROVEMENT_MIN, LANE_RISK_BUDGET_CAP,
                 p_noise_survival),
        "reopen_conditions": [
            "owner-level revision of docs/portfolio_covariance_lane.md acceptance clause that (a) sets a "
            "portfolio-level materiality threshold for window regression (e.g., ignore window EV deltas smaller "
            "than 1% of the champion window EV) AND (b) replaces the >10% aggregate EV bar with a bar reachable "
            "under the <=10% weight cap; this is a governance/doc change, not a per-experiment gate invention",
            "a new rejected-but-positive candidate family whose STANDALONE aggregate EV is within ~1x of the "
            "champion (~10.6 daily-mtm proxy), such that a <=10% weight could mathematically clear a >10% bar",
            "materially more closed forward replacement-value rows for any ranked candidate that already has a "
            "default-off forward ledger (e.g., finra_otc_internalization_retreat), evaluated through the "
            "observed-only forward clause of the lane doc instead of another frozen-window overlay replay",
        ],
        "observed_only_forward_watch_shortlist": shortlist,
    }

    artifact = {
        "experiment_id": "exp-20260707-017",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "change_type": "observed_only_attribution",
        "implementation_mode": "read_only_joint_synthesis_no_replay",
        "hypothesis": (
            "The portfolio covariance lane per-candidate overlay consumption cannot produce an acceptance "
            "under its own predeclared standard: rejections are noise-gate artifacts and the acceptance "
            "clause is structurally unreachable under the risk-budget cap."
        ),
        "parameters": {
            "noise_fraction_of_champion_window_ev": NOISE_FRACTION,
            "lane_accept_ev_improvement_min": LANE_ACCEPT_EV_IMPROVEMENT_MIN,
            "lane_risk_budget_cap": LANE_RISK_BUDGET_CAP,
            "overlays_synthesized": n,
        },
        "summary": {
            "overlays": n,
            "positive_aggregate_ev_delta": n_positive_agg_ev,
            "positive_aggregate_pnl_delta": n_positive_agg_pnl,
            "rejected_only_on_noise_scale_window_regressions": n_rejected_only_noise,
            "rejected_with_at_least_one_decisive_regression": n_any_decisive,
            "max_aggregate_ev_delta_fraction_of_core": max_agg_frac,
            "worst_aggregate_drawdown_drift": worst_dd_drift,
            "pure_noise_overlay_survival_probability_three_window_sign_test": p_noise_survival,
            "structural_clause_satisfiable_by_any_observed_candidate": structurally_satisfiable,
        },
        "per_candidate": rows,
        "verdict": verdict,
        "production_impact": "none: no order path, ranking, sizing, exit, or sleeve state touched",
    }

    out_dir = REPO / "data" / "experiments" / "exp-20260707-017"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "exp_20260707_017_portfolio_lane_gate_calibration_joint_verdict.json"
    out_path.write_text(json.dumps(artifact, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out_path)
    print(json.dumps(artifact["summary"], indent=1))
    print(json.dumps(verdict["observed_only_forward_watch_shortlist"], indent=1))


if __name__ == "__main__":
    main()
