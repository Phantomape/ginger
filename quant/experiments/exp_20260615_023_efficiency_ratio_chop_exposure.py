"""exp-20260615-023: Efficiency-Ratio chop axis + continuous exposure scalar.

Follow-on to exp-20260615-019. That diagnostic found both an accepted sleeve
(Fundamental Growth + RS) and the rejected deferred-revenue scout lose
specifically in the directionless `choppy_range` regime, NOT in stress, and that
a monotonic `risk_off_score` tilt would not help (Spearman ~ 0).

Industry practice for the "directionless" axis is a battle-tested, single
-parameter, PIT measure of directional efficiency. This experiment swaps the
ad-hoc bull/stress chop label for Kaufman's Efficiency Ratio (ER) of SPY and
emits a continuous exposure scalar (vol-target style: size by trendiness, never
a hard on/off gate), then re-runs the same read-only attribution to test whether
ER separates winning vs losing trades MORE cleanly than the 3-regime label.

ER over N sessions = |close[t] - close[t-N]| / sum_{j}( |close[j] - close[j-1]| ).
ER -> 1 means a clean directional move (trend, including a clean stress selloff);
ER -> 0 means choppy/directionless. exposure_scalar = floor + (1-floor)*ER.

Constants (ER window 20, exposure floor 0.5) are conventional and NOT optimized
against the trade PnL attributed below. Read-only: no production code, shared
adapter, orders, ranking, sizing, exits, LLM/news, or watchlist change. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant" / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import experiment_registry  # noqa: E402
import exp_20260615_019_pit_regime_state_attribution as base019  # noqa: E402

EXPERIMENT_ID = "exp-20260615-023"
STEM = "efficiency_ratio_chop_exposure"
CHANGED_VARIABLE = "efficiency_ratio_chop_axis_and_continuous_exposure_scalar"
RULE_VERSION = "efficiency_ratio_chop_exposure_v1"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_023_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = base019.WINDOWS
_round = base019._round
_spearman = base019._spearman

ER_WINDOW = 20
EXPOSURE_FLOOR = 0.5


def _efficiency_ratio_by_date(ohlcv: dict[str, Any], window: int = ER_WINDOW) -> tuple[dict[str, float], list[str]]:
    rows = base019._series(ohlcv, "SPY")
    dates = [str(b["Date"])[:10] for b in rows]
    closes = [float(b["Close"]) for b in rows]
    out: dict[str, float] = {}
    for i in range(len(rows)):
        if i < window:
            continue
        net = abs(closes[i] - closes[i - window])
        denom = sum(abs(closes[j] - closes[j - 1]) for j in range(i - window + 1, i + 1))
        if denom > 0:
            out[dates[i]] = net / denom
    return out, dates


def _exposure_scalar(er: float) -> float:
    return EXPOSURE_FLOOR + (1.0 - EXPOSURE_FLOOR) * max(0.0, min(1.0, er))


def _er_for_trade(er_by_window: dict[str, dict[str, float]], window_label: str, signal_date: str) -> float | None:
    er_map = er_by_window[window_label]
    if signal_date in er_map:
        return er_map[signal_date]
    # fall back to latest ER date <= signal_date
    best = None
    best_date = ""
    for d, v in er_map.items():
        if d <= signal_date and d >= best_date:
            best, best_date = v, d
    return best


def _summ(pnls: list[float]) -> dict[str, Any]:
    if not pnls:
        return {"count": 0, "total_pnl": 0.0, "mean_pnl": None, "win_rate": None}
    wins = sum(1 for p in pnls if p > 0)
    return {
        "count": len(pnls),
        "total_pnl": _round(sum(pnls), 2),
        "mean_pnl": _round(sum(pnls) / len(pnls), 2),
        "win_rate": _round(wins / len(pnls), 4),
    }


def _attribute_by_er(
    trades_by_window: dict[str, list[dict[str, Any]]],
    er_by_window: dict[str, dict[str, float]],
) -> dict[str, Any]:
    er_pnl: list[tuple[float, float]] = []
    er_pnl_by_window: dict[str, list[tuple[float, float]]] = {label: [] for label in WINDOWS}
    missing = 0
    total = 0
    for label, trades in trades_by_window.items():
        for tr in trades:
            total += 1
            er = _er_for_trade(er_by_window, label, tr["signal_date"])
            if er is None:
                missing += 1
                continue
            er_pnl.append((er, tr["pnl"]))
            er_pnl_by_window[label].append((er, tr["pnl"]))

    def _terciles(pairs: list[tuple[float, float]]) -> dict[str, Any]:
        if len(pairs) < 6:
            return {"insufficient_sample": True, "n": len(pairs)}
        ers = sorted(e for e, _ in pairs)
        n = len(ers)
        q1 = ers[n // 3]
        q2 = ers[(2 * n) // 3]
        low, mid, high = [], [], []
        for e, p in pairs:
            if e <= q1:
                low.append(p)
            elif e <= q2:
                mid.append(p)
            else:
                high.append(p)
        return {
            "er_q1": _round(q1, 4),
            "er_q2": _round(q2, 4),
            "low_er_chop": _summ(low),
            "mid_er": _summ(mid),
            "high_er_trend": _summ(high),
        }

    # soft-tilt counterfactual (within-sample, observe-only): size each trade by
    # exposure_scalar(ER) and compare capital efficiency vs unweighted.
    unweighted = [p for _e, p in er_pnl]
    sum_scalar = sum(_exposure_scalar(e) for e, _ in er_pnl)
    weighted_total = sum(_exposure_scalar(e) * p for e, p in er_pnl)
    pnl_per_unit_exposure = weighted_total / sum_scalar if sum_scalar > 0 else None
    unweighted_mean = (sum(unweighted) / len(unweighted)) if unweighted else None

    return {
        "total_trades": total,
        "missing_er_trades": missing,
        "spearman_er_vs_pnl": _spearman([e for e, _ in er_pnl], [p for _e, p in er_pnl]),
        "er_terciles_overall": _terciles(er_pnl),
        "er_terciles_by_window": {label: _terciles(er_pnl_by_window[label]) for label in WINDOWS},
        "soft_tilt_counterfactual_observe_only": {
            "note": (
                "Within-sample only. Sizes each trade's notional by "
                "exposure_scalar=floor+(1-floor)*ER; compares capital efficiency "
                "vs unweighted. Not acceptance evidence."
            ),
            "exposure_floor": EXPOSURE_FLOOR,
            "unweighted_mean_pnl": _round(unweighted_mean, 2),
            "exposure_weighted_pnl_per_unit_exposure": _round(pnl_per_unit_exposure, 2),
            "capital_efficiency_gain_usd_per_unit": _round(
                (pnl_per_unit_exposure - unweighted_mean) if (pnl_per_unit_exposure is not None and unweighted_mean is not None) else None, 2
            ),
            "unweighted_total_pnl": _round(sum(unweighted), 2),
            "exposure_weighted_total_pnl": _round(weighted_total, 2),
        },
    }


def _er_day_distribution(er_by_window: dict[str, dict[str, float]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    allvals: list[float] = []
    for label, (start, end, _path) in WINDOWS.items():
        vals = [v for d, v in er_by_window[label].items() if start <= d <= end]
        allvals.extend(vals)
        out[label] = {
            "days": len(vals),
            "mean_er": _round(sum(vals) / len(vals), 4) if vals else None,
            "frac_low_er_below_0p30": _round(sum(1 for v in vals if v < 0.30) / len(vals), 4) if vals else None,
        }
    out["all_windows_mean_er"] = _round(sum(allvals) / len(allvals), 4) if allvals else None
    return out


def _build_payload() -> dict[str, Any]:
    er_by_window: dict[str, dict[str, float]] = {}
    for label, (_s, _e, path) in WINDOWS.items():
        ohlcv = json.loads((REPO_ROOT / path).read_text(encoding="utf-8")).get("ohlcv") or {}
        er_map, _dates = _efficiency_ratio_by_date(ohlcv, ER_WINDOW)
        er_by_window[label] = er_map

    fgrs = base019._load_window_trades(base019.FGRS_SOURCE_ARTIFACT, ("pnl_without_low_liability_support", "pnl"))
    deferred = base019._load_window_trades(base019.DEFERRED_REVENUE_ARTIFACT, ("pnl", "paper_pnl"))

    fgrs_attr = _attribute_by_er(fgrs, er_by_window)
    deferred_attr = _attribute_by_er(deferred, er_by_window)
    er_days = _er_day_distribution(er_by_window)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": base019._utc_now(),
        "lane": "measurement_repair",
        "status": "observed_only",
        "decision": "measurement_repair_efficiency_ratio_chop_axis_and_exposure_scalar_built",
        "accepted": False,
        "accepted_alpha": False,
        "change_type": "identity_or_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": "pit_efficiency_ratio_chop_axis_diagnostic",
        "rule_version": RULE_VERSION,
        "builds_on": "exp-20260615-019",
        "hypothesis": (
            "Kaufman Efficiency Ratio of SPY (directional efficiency) is a cleaner "
            "PIT chop axis than the ad-hoc bull/stress regime label; a continuous "
            "exposure scalar (floor+(1-floor)*ER) is the vol-target-style soft "
            "tilt suggested by industry practice, not a hard on/off gate."
        ),
        "leakage_discipline": (
            "ER window (20) and exposure floor (0.5) are conventional, set by hand, "
            "NOT optimized against the attributed trade PnL. ER reads only SPY "
            "closes on or before the signal date."
        ),
        "efficiency_ratio_spec": {
            "rule_version": RULE_VERSION,
            "er_window": ER_WINDOW,
            "exposure_floor": EXPOSURE_FLOOR,
            "exposure_scalar_formula": "floor + (1-floor) * clip(ER,0,1)",
            "interpretation": "ER->1 clean trend (incl. clean stress move); ER->0 directionless chop.",
        },
        "efficiency_ratio_day_distribution": er_days,
        "attribution": {
            "fundamental_growth_rs_low_liability": {
                "trade_source": base019._repo_rel(base019.FGRS_SOURCE_ARTIFACT),
                **fgrs_attr,
            },
            "deferred_revenue_demand_acceleration_exp017": {
                "trade_source": base019._repo_rel(base019.DEFERRED_REVENUE_ARTIFACT),
                **deferred_attr,
            },
        },
        "comparison_to_exp019": {
            "exp019_spearman_risk_off_vs_pnl_fgrs": -0.0444,
            "exp019_spearman_risk_off_vs_pnl_deferred": 0.0851,
            "this_run_spearman_er_vs_pnl_fgrs": fgrs_attr["spearman_er_vs_pnl"],
            "this_run_spearman_er_vs_pnl_deferred": deferred_attr["spearman_er_vs_pnl"],
            "note": (
                "A materially more positive Spearman(ER, PnL) than the ~0 "
                "Spearman(risk_off_score, PnL) confirms the loss axis is "
                "directionless chop and that ER captures it; a still-near-zero ER "
                "Spearman would mean ER is not the right chop measure either."
            ),
        },
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": False,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
            "uses_llm": False,
            "parity_note": (
                "Diagnostic only. Promoting the ER exposure scalar to a portfolio "
                "soft tilt requires a shared daily ER artifact, a parity test, and "
                "forward state-tagged replacement-value rows (or the manual live "
                "pilot scorecard), never a hard per-window gate."
            ),
        },
        "next_evidence_needed": (
            "If Spearman(ER, PnL) is clearly positive and low-ER mean PnL is "
            "negative in the windows with chop samples, promote ER to a shared "
            "daily regime artifact and apply the continuous exposure scalar as a "
            "portfolio-level soft tilt, validated on forward rows / live-pilot "
            "scorecard. Do not tune ER window or exposure floor on frozen windows."
        ),
        "related_files": [
            base019._repo_rel(Path(__file__)),
            base019._repo_rel(OUT_JSON),
            base019._repo_rel(LOG_JSON),
            base019._repo_rel(TICKET_JSON),
            base019._repo_rel(CARD_MD),
            base019._repo_rel(MANIFEST_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    def _tbl(attr: dict[str, Any]) -> list[str]:
        t = attr["er_terciles_overall"]
        if t.get("insufficient_sample"):
            return ["(insufficient sample)"]
        rows = [
            "| ER bucket | trades | total PnL | mean PnL | win rate |",
            "|---|---:|---:|---:|---:|",
        ]
        for key, lab in (("low_er_chop", "low ER (chop)"), ("mid_er", "mid ER"), ("high_er_trend", "high ER (trend)")):
            s = t[key]
            rows.append(f"| {lab} | {s['count']} | {s['total_pnl']} | {s['mean_pnl']} | {s['win_rate']} |")
        return rows

    fa = payload["attribution"]["fundamental_growth_rs_low_liability"]
    da = payload["attribution"]["deferred_revenue_demand_acceleration_exp017"]
    lines = [
        f"# {EXPERIMENT_ID} Efficiency-Ratio Chop Axis + Exposure Scalar",
        "",
        f"Status: `{payload['status']}`  Lane: `measurement_repair`  Builds on: `exp-20260615-019`",
        "",
        "## What was built",
        "",
        "Kaufman Efficiency Ratio (ER, window 20) of SPY as the PIT chop axis, plus "
        "a continuous exposure scalar `floor + (1-floor)*ER` (floor 0.5). Re-ran the "
        "exp-019 read-only attribution bucketed by ER. Zero execution change.",
        "",
        "## ER day distribution",
        "",
        "```",
        json.dumps(payload["efficiency_ratio_day_distribution"], indent=2, sort_keys=True),
        "```",
        "",
        "## Fundamental Growth + RS — by ER bucket",
        "",
        *_tbl(fa),
        "",
        f"- Spearman(ER, PnL): `{fa['spearman_er_vs_pnl']}`  (exp-019 Spearman vs risk_off_score: `-0.0444`)",
        f"- soft-tilt capital-efficiency gain: `{fa['soft_tilt_counterfactual_observe_only']['capital_efficiency_gain_usd_per_unit']}` USD/unit (within-sample, observe-only)",
        "",
        "## Deferred-revenue (exp-017) — by ER bucket",
        "",
        *_tbl(da),
        "",
        f"- Spearman(ER, PnL): `{da['spearman_er_vs_pnl']}`  (exp-019 Spearman vs risk_off_score: `0.0851`)",
        "",
        "## Leakage discipline",
        "",
        payload["leakage_discipline"],
        "",
        "## Next evidence",
        "",
        payload["next_evidence_needed"],
        "",
        "No JavaScript was used.",
    ]
    return "\n".join(lines) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    fa = payload["attribution"]["fundamental_growth_rs_low_liability"]
    da = payload["attribution"]["deferred_revenue_demand_acceleration_exp017"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "measurement_repair",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "changed_variable": CHANGED_VARIABLE,
        "builds_on": "exp-20260615-019",
        "hypothesis": payload["hypothesis"],
        "spearman_er_vs_pnl_fgrs": fa["spearman_er_vs_pnl"],
        "spearman_er_vs_pnl_deferred": da["spearman_er_vs_pnl"],
        "comparison_to_exp019": payload["comparison_to_exp019"],
        "production_impact": payload["production_impact"],
        "artifact": base019._repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _persist(payload: dict[str, Any]) -> None:
    base019._write_json(OUT_JSON, payload)
    base019._write_json(LOG_JSON, payload)
    base019._write_text(CARD_MD, _build_card(payload))
    experiment_registry.append_log_entry(EXPERIMENT_LOG, _build_log_record(payload))
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": base019._repo_rel(OUT_JSON),
        "log": base019._repo_rel(LOG_JSON),
        "comparison_to_exp019": payload["comparison_to_exp019"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "summary": payload["decision"],
        "artifact": base019._repo_rel(OUT_JSON),
        "log": base019._repo_rel(LOG_JSON),
        "ticket_file": base019._repo_rel(TICKET_JSON),
        "card_file": base019._repo_rel(CARD_MD),
        "revision_manifest_file": base019._repo_rel(MANIFEST_JSON),
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            base019._repo_rel(Path(__file__)),
            base019._repo_rel(OUT_JSON),
            base019._repo_rel(CARD_MD),
            base019._repo_rel(MANIFEST_JSON),
            base019._repo_rel(TICKET_JSON),
            base019._repo_rel(LOG_JSON),
            base019._repo_rel(EXPERIMENT_LOG),
            base019._repo_rel(REGISTRY_JSON),
        ],
    }
    base019._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "er_day_distribution": payload["efficiency_ratio_day_distribution"],
        "comparison_to_exp019": payload["comparison_to_exp019"],
        "fgrs_er_terciles": payload["attribution"]["fundamental_growth_rs_low_liability"]["er_terciles_overall"],
        "deferred_er_terciles": payload["attribution"]["deferred_revenue_demand_acceleration_exp017"]["er_terciles_overall"],
        "fgrs_soft_tilt": payload["attribution"]["fundamental_growth_rs_low_liability"]["soft_tilt_counterfactual_observe_only"],
    }, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
