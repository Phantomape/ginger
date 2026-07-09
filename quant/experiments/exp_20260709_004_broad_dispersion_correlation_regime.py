"""exp-20260709-004: broad-universe dispersion/correlation regime diagnostic.

Alpha search, read-only diagnostic (owner priority: probabilistic, multi-level
regime state; broad-universe MEASUREMENT only — the trading universe stays
frozen). Tests whether cross-sectional structure separates the single chop
label into two sub-regimes with opposite strategy payoffs, using daily
long-short decile proxies (~hundreds of daily observations instead of 33
chop days):

- Claim A: higher average pairwise correlation -> weaker next-day 20d-momentum
  decile spread (Spearman < 0);
- Claim B: higher cross-sectional dispersion -> stronger next-day 1d-reversal
  decile spread (Spearman > 0).

Predeclared verdict rule: a claim passes if the pooled Spearman sign matches,
pooled |t| >= 2, and the per-window sign matches in >= 2 of 3 canonical
windows. >= 1 claim passing -> observed_only LEAD (feeds a regime-v2 feature
experiment); none -> observed_only_rejected. This diagnostic can never be
accepted alpha by itself (AGENTS.md: diagnostics are not acceptance evidence).
Analysis stops at 2026-04-21: most of the broad warehouse froze 2026-04-24.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

EXPERIMENT_ID = "exp-20260709-004"
OWNER = "interactive"
LANE = "alpha_search"
SLUG = "broad_dispersion_correlation_regime"
RUNNER = f"quant/experiments/exp_20260709_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import pandas as pd  # noqa: E402

from broad_dispersion_features import (  # noqa: E402
    FEATURES_RULE_VERSION,
    avg_pairwise_correlation,
    corr_t_stat,
    cross_sectional_dispersion,
    daily_returns,
    liquidity_mask,
    load_broad_panel,
    momentum_spread_next_day,
    quartile_means,
    reversal_spread_next_day,
    spearman,
)
from chop_mean_reversion_sleeve import breadth_by_date, regime_labels_by_date  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from filter import WATCHLIST  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_MAIN = DATA_DIR / "warehouse" / "warehouse_main.sqlite"
WAREHOUSE_HOT = DATA_DIR / "warehouse" / "warehouse_main_hot.sqlite"

PANEL_START = "2024-06-01"  # warm-up for ADV/corr/momentum lookbacks
ANALYSIS_END = "2026-04-21"  # broad universe largely frozen 2026-04-24
CANONICAL_WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
]
MIN_ABS_T = 2.0
MIN_SIGN_CONSISTENT_WINDOWS = 2

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260709_004_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "One chop label mixes two structurally different states - dead chop (high "
    "average pairwise correlation, low dispersion) and stock-picker chop "
    "(stocks trending apart under a flat index). Broad-universe cross-sectional "
    "dispersion and average pairwise correlation should separate the daily "
    "payoff of momentum vs reversal long-short proxies."
)
CHANGED_VARIABLE = "broad_dispersion_correlation_regime_axis_v1"
MECHANISM_FAMILY = "dispersion_correlation_regime_structure"
TRIAL_FAMILY = "broad_dispersion_regime_diagnostic"
TRIAL_VARIANT_ID = "broad_dispersion_corr_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260708-023",
    "exp-20260708-025",
    "exp-20260615-019",
    "exp-20260615-023",
    "exp-20260627-016",
]
CAUSAL_COMPONENTS = [
    "liquid_broad_universe_daily_panel",
    "cross_sectional_dispersion_feature",
    "avg_pairwise_correlation_identity_feature",
    "momentum_and_reversal_daily_proxy_spreads",
    "p_choppy_interaction_attribution",
]
PREDICTED_FAILURE_MODES = [
    "dispersion_and_corr_collinear_with_existing_vol_features",
    "proxy_spreads_dominated_by_microcap_noise",
    "signs_not_stable_across_windows",
    "pchop_interaction_too_weak_to_matter",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def load_watchlist_bars() -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    for wh in (WAREHOUSE_MAIN, WAREHOUSE_HOT):
        if not wh.exists():
            continue
        con = sqlite3.connect(f"file:{wh.resolve().as_posix()}?mode=ro", uri=True)
        try:
            placeholders = ",".join("?" for _ in WATCHLIST)
            for t, d, o, h, l, c in con.execute(
                "select ticker, date, open, high, low, close from ohlcv "
                f"where ticker in ({placeholders})",
                list(WATCHLIST),
            ):
                if c is None:
                    continue
                rows.setdefault(str(t).upper(), {})[str(d)[:10]] = {
                    "Date": str(d)[:10],
                    "Open": float(o) if o is not None else float(c),
                    "High": float(h) if h is not None else float(c),
                    "Low": float(l) if l is not None else float(c),
                    "Close": float(c),
                }
        finally:
            con.close()
    return {t: [by_d[d] for d in sorted(by_d)] for t, by_d in rows.items() if by_d}


def evaluate_claim(
    name: str,
    feature: pd.Series,
    outcome: pd.Series,
    expected_sign: int,
    window_masks: dict[str, pd.Series],
) -> dict[str, Any]:
    frame = pd.DataFrame({"f": feature, "o": outcome}).dropna()
    pooled_r = spearman(frame["f"].tolist(), frame["o"].tolist())
    pooled_t = corr_t_stat(pooled_r, len(frame))
    per_window = {}
    sign_hits = 0
    for wname, mask in window_masks.items():
        sub = frame[frame.index.isin(mask.index[mask])]
        r = spearman(sub["f"].tolist(), sub["o"].tolist())
        t = corr_t_stat(r, len(sub))
        sign_ok = r is not None and (r > 0) == (expected_sign > 0) and r != 0
        sign_hits += int(bool(sign_ok))
        per_window[wname] = {
            "n": int(len(sub)),
            "spearman": round(r, 4) if r is not None else None,
            "t": round(t, 2) if t is not None else None,
            "sign_matches": bool(sign_ok),
        }
    pooled_sign_ok = pooled_r is not None and (pooled_r > 0) == (expected_sign > 0)
    passed = bool(
        pooled_sign_ok
        and pooled_t is not None
        and abs(pooled_t) >= MIN_ABS_T
        and sign_hits >= MIN_SIGN_CONSISTENT_WINDOWS
    )
    return {
        "claim": name,
        "expected_sign": expected_sign,
        "n": int(len(frame)),
        "pooled_spearman": round(pooled_r, 4) if pooled_r is not None else None,
        "pooled_t": round(pooled_t, 2) if pooled_t is not None else None,
        "sign_consistent_windows": sign_hits,
        "per_window": per_window,
        "quartiles": quartile_means(feature, outcome),
        "passed": passed,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()

    closes, dollar = load_broad_panel(
        [str(WAREHOUSE_MAIN.resolve().as_posix())], PANEL_START, ANALYSIS_END
    )
    panel_shape = list(closes.shape)
    mask = liquidity_mask(closes, dollar)
    returns = daily_returns(closes)
    dispersion = cross_sectional_dispersion(returns, mask)
    avg_corr = avg_pairwise_correlation(returns, mask)
    mom_next = momentum_spread_next_day(returns, closes, mask)
    rev_next = reversal_spread_next_day(returns, mask)
    eligible_per_day = mask.sum(axis=1)

    # p_choppy (continuous) from the validated market-level module.
    wl_bars = load_watchlist_bars()
    spy_bars = wl_bars.get("SPY") or []
    all_days = [b["Date"] for b in spy_bars if PANEL_START <= b["Date"] <= ANALYSIS_END]
    breadth = breadth_by_date(wl_bars, all_days)
    labels = regime_labels_by_date(spy_bars, breadth, all_days)
    p_chop = pd.Series(
        {d: (labels.get(d) or {}).get("p_choppy_range") for d in all_days}, dtype=float
    )

    analysis_days = [
        d for d in closes.index
        if any(start <= d <= end for _, start, end in CANONICAL_WINDOWS)
    ]
    in_analysis = pd.Series(True, index=analysis_days)
    window_masks = {
        name: pd.Series(True, index=[d for d in analysis_days if start <= d <= end])
        for name, start, end in CANONICAL_WINDOWS
    }

    def _scope(series: pd.Series) -> pd.Series:
        return series[series.index.isin(in_analysis.index)]

    claim_a = evaluate_claim(
        "higher_avg_corr_weakens_momentum_spread",
        _scope(avg_corr), _scope(mom_next), expected_sign=-1, window_masks=window_masks,
    )
    claim_b = evaluate_claim(
        "higher_dispersion_strengthens_reversal_spread",
        _scope(dispersion), _scope(rev_next), expected_sign=+1, window_masks=window_masks,
    )

    # Attribution only: does the structure matter MORE when p_choppy is high?
    interaction: dict[str, Any] = {}
    joined = pd.DataFrame(
        {"p": p_chop, "corr": avg_corr, "disp": dispersion, "mom": mom_next, "rev": rev_next}
    ).dropna()
    joined = joined[joined.index.isin(in_analysis.index)]
    if len(joined) >= 60:
        hi = joined[joined["p"] >= joined["p"].quantile(2 / 3)]
        lo = joined[joined["p"] <= joined["p"].quantile(1 / 3)]
        interaction = {
            "n_high_pchop": int(len(hi)),
            "n_low_pchop": int(len(lo)),
            "corr_vs_mom_spearman_high_pchop": spearman(hi["corr"].tolist(), hi["mom"].tolist()),
            "corr_vs_mom_spearman_low_pchop": spearman(lo["corr"].tolist(), lo["mom"].tolist()),
            "disp_vs_rev_spearman_high_pchop": spearman(hi["disp"].tolist(), hi["rev"].tolist()),
            "disp_vs_rev_spearman_low_pchop": spearman(lo["disp"].tolist(), lo["rev"].tolist()),
            "note": "attribution only; not part of the pass/fail rule",
        }

    claims_passed = [c["claim"] for c in (claim_a, claim_b) if c["passed"]]

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if closes.empty or float(eligible_per_day.max() or 0) < 300:
        measurement_blockers.append("broad_panel_too_thin")
    if claim_a["n"] < 200:
        measurement_blockers.append("too_few_daily_observations")

    measurement_passed = not measurement_blockers
    if not measurement_passed:
        status, decision = "blocked", f"blocked_{SLUG}"
    elif claims_passed:
        status = "observed_only"
        decision = f"observed_only_lead_{SLUG}"
    else:
        status = "observed_only"
        decision = f"observed_only_rejected_{SLUG}"

    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "panel_shape": panel_shape,
        "max_eligible_names_per_day": int(eligible_per_day.max() or 0),
        "daily_observations": claim_a["n"],
        "claim_a_pooled_spearman": claim_a["pooled_spearman"],
        "claim_a_pooled_t": claim_a["pooled_t"],
        "claim_a_passed": claim_a["passed"],
        "claim_b_pooled_spearman": claim_b["pooled_spearman"],
        "claim_b_pooled_t": claim_b["pooled_t"],
        "claim_b_passed": claim_b["passed"],
        "claims_passed": claims_passed,
    }
    success_probability = float(
        (ticket.get("prediction") or {}).get("success_probability") or 0.4
    )
    prediction = {
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": PREDICTED_FAILURE_MODES,
        "confidence_reason": (ticket.get("prediction") or {}).get("confidence_reason"),
    }
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": 1 if claims_passed else 0,
        "brier_score": round(
            (success_probability - (1.0 if claims_passed else 0.0)) ** 2, 6
        ),
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_modes": (
            measurement_blockers
            + ([] if claims_passed else ["signs_not_stable_across_windows"])
        ),
        "predicted_failure_mode_hit": not claims_passed,
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "read_only_broad_universe_regime_diagnostic",
    }
    files = [
        "quant/broad_dispersion_features.py",
        "quant/test_broad_dispersion_features.py",
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "accepted_measurement_repair": False,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "strategy_logic",
        "implementation_mode": "read_only_diagnostic_lead_generation",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_data_axis_broad_universe_cross_sectional_structure",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260708-023/-025": "Both chop trading bundles starved on 33 chop days; this fixes the sample axis (daily proxies).",
                "exp-20260615-023": "Kaufman ER chop axis rejected; dispersion/correlation is a different, cross-sectional construct.",
                "exp-20260627-016": "Universe expansion for TRADING rejected; this is measurement-only broadening.",
                "novelty_gate": "Override accepted: broad cross-sectional structure + daily proxy outcome are new axes.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "A claim passes if pooled Spearman sign matches the predeclared "
                f"direction, pooled |t| >= {MIN_ABS_T}, and >= {MIN_SIGN_CONSISTENT_WINDOWS}/3 "
                "windows agree in sign. >= 1 claim -> observed_only lead; none -> "
                "observed_only_rejected. Never accepted alpha by itself."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "features_rule_version": FEATURES_RULE_VERSION,
            "panel_start": PANEL_START,
            "analysis_end": ANALYSIS_END,
            "liquidity": "close >= $5, top 800 by 20d avg dollar volume",
            "corr_estimator": "equal-weight portfolio variance identity, 20d window",
            "momentum_proxy": "t-21 -> t-1 return deciles, next-day top-minus-bottom",
            "reversal_proxy": "day-t return deciles, next-day bottom-minus-top",
            "frozen_universe_caveat": "broad warehouse largely frozen 2026-04-24; analysis ends 04-21",
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": measurement_passed,
            "fields_checked": ["close", "volume", "date", "ticker", "p_choppy_range"],
            "entry_date_scope": "No trades and no signal objects; daily proxy spreads only.",
            "target_price_scope": "Not applicable; read-only diagnostic.",
        },
        "gate3": {
            "passed": measurement_passed,
            "filter_added": False,
            "signals_generated": claim_a["n"],
            "signals_survived": claim_a["n"],
            "survival_rate": 1.0 if claim_a["n"] else None,
            "note": "Daily observations, not signals; no production filter touched.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": [] if claims_passed else ["no_claim_cleared_predeclared_bar"],
            "measurement_repair_only": False,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "claims": {"claim_a": claim_a, "claim_b": claim_b},
        "p_chop_interaction": interaction,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": None,
            "forbidden_near_neighbor_retry": (
                "Do not re-run with tweaked liquidity cuts, decile counts, lookbacks, "
                "or alternative dispersion definitions on the same frozen windows. "
                "If lead: next step is a regime-v2 feature experiment adding "
                "dispersion and average-correlation inputs to regime_chop_state, "
                "then sleeve-scoped validation on forward rows. If rejected: the "
                "cross-sectional axis needs a different outcome variable (for example "
                "sleeve forward rows), not a re-slice."
            ),
            "new_evidence_required": (
                "Forward rows tagged with dispersion/corr state, or a structurally "
                "different cross-sectional construct (e.g. sector-level dispersion)."
            ),
        },
        "next_retry_requires": [
            "no same-window re-slices of dispersion/corr definitions",
            "lead -> regime-v2 feature experiment; rejected -> new outcome variable",
        ],
        "changed_files": files,
        "related_files": [
            "quant/regime_chop_state.py",
            "quant/chop_mean_reversion_sleeve.py",
            "experiments/cards/exp-20260708-025.md",
        ],
        "allowed_write_scope": files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_broad_dispersion_features.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": measurement_passed,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def finalize_reflection(payload: dict[str, Any]) -> None:
    a = payload["claims"]["claim_a"]
    b = payload["claims"]["claim_b"]
    if payload["delta_metrics"]["claims_passed"]:
        why = (
            f"Cross-sectional structure carries regime signal: corr->momentum Spearman "
            f"{a['pooled_spearman']} (t={a['pooled_t']}, passed={a['passed']}), "
            f"disp->reversal Spearman {b['pooled_spearman']} (t={b['pooled_t']}, "
            f"passed={b['passed']}) over {a['n']} daily observations. The chop label "
            "can be decomposed; next step is regime-v2 features + sleeve-scoped "
            "forward validation."
        )
    else:
        why = (
            f"Neither predeclared claim cleared the bar (corr->mom {a['pooled_spearman']} "
            f"t={a['pooled_t']}; disp->rev {b['pooled_spearman']} t={b['pooled_t']}); "
            "on this liquid panel the cross-sectional axis does not separate daily "
            "momentum/reversal payoffs strongly enough to justify a regime-v2 feature."
        )
    payload["post_run_reflection"]["why_result_happened"] = why


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    a = payload["claims"]["claim_a"]
    b = payload["claims"]["claim_b"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: broad dispersion/correlation regime diagnostic",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Daily observations: `{delta['daily_observations']}` (eligible names/day up to `{delta['max_eligible_names_per_day']}`)",
            f"- Claim A corr->momentum: Spearman `{a['pooled_spearman']}` t `{a['pooled_t']}` windows `{a['sign_consistent_windows']}/3` passed `{a['passed']}`",
            f"- Claim B disp->reversal: Spearman `{b['pooled_spearman']}` t `{b['pooled_t']}` windows `{b['sign_consistent_windows']}/3` passed `{b['passed']}`",
            f"- Claim A quartiles (bps): `{a['quartiles'].get('quartile_mean_bps')}`",
            f"- Claim B quartiles (bps): `{b['quartiles'].get('quartile_mean_bps')}`",
            "- Strategy behavior changed: `false` (read-only diagnostic)",
            "",
            "## Why",
            "",
            payload["post_run_reflection"]["why_result_happened"] or "",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        QUANT_ROOT / "broad_dispersion_features.py",
        QUANT_ROOT / "test_broad_dispersion_features.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "accepted_measurement_repair": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    finalize_reflection(payload)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "claims": payload["claims"],
                "p_chop_interaction": payload["p_chop_interaction"],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
