"""exp-20260615-025: re-validate the chop separation through the SHARED module.

Shared-paper-first discipline: the exp-20260615-019 chop finding is only a lead
until a shared helper reproduces it. This runner imports the new shared module
`quant.regime_chop_state` and re-runs the read-only chop attribution on the same
accepted-sleeve replay trades, at TWO fidelities:

- FULL: trend + breadth + index-agreement + drawdown + vol (what replay and any
  bar-having daily caller can supply). Must reproduce the exp-019 separation.
- THIN: trend + 20d momentum only (the production market-state context's
  replayable subset, minus VIX which the canonical snapshots lack). This is a
  LOWER BOUND on the production daily field and tells us whether breadth/stress
  are load-bearing.

Read-only. No production order, ranking, sizing, exit, or watchlist change. No
JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import experiment_registry  # noqa: E402
import exp_20260615_019_pit_regime_state_attribution as base019  # noqa: E402
import regime_chop_state as rc  # noqa: E402

EXPERIMENT_ID = "exp-20260615-025"
STEM = "regime_chop_shared_promotion"
CHANGED_VARIABLE = "shared_pit_regime_chop_exposure_scalar"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_025_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = base019.WINDOWS
_round = base019._round
_spearman = base019._spearman


def _models() -> dict[str, base019.RegimeModel]:
    models: dict[str, base019.RegimeModel] = {}
    for label, (_s, _e, path) in WINDOWS.items():
        ohlcv = json.loads((REPO_ROOT / path).read_text(encoding="utf-8")).get("ohlcv") or {}
        models[label] = base019.RegimeModel(ohlcv)
    return models


def _index_agreement(model: base019.RegimeModel, date: str) -> float:
    hits = sum(1 for t in base019.INDEX_TICKERS if model._idx_ret20.get(t, {}).get(date, 0.0) > 0)
    return hits / len(base019.INDEX_TICKERS)


def _spy_bars(model: base019.RegimeModel) -> list[dict[str, Any]]:
    return [{"Date": d, "Close": c, "High": h} for d, c, h in zip(model.dates, model.closes, model.highs)]


def _summ(pnls: list[float]) -> dict[str, Any]:
    if not pnls:
        return {"count": 0, "mean_pnl": None, "win_rate": None}
    wins = sum(1 for p in pnls if p > 0)
    return {"count": len(pnls), "mean_pnl": _round(sum(pnls) / len(pnls), 2), "win_rate": _round(wins / len(pnls), 4)}


def _attribute(trades_by_window: dict[str, list[dict[str, Any]]], models: dict[str, base019.RegimeModel]) -> dict[str, Any]:
    full_label_pnls: dict[str, list[float]] = defaultdict(list)
    full_pchop_pnl: list[tuple[float, float]] = []
    thin_pchop_pnl: list[tuple[float, float]] = []
    exposure_by_label: dict[str, list[float]] = defaultdict(list)
    n = 0
    for label, trades in trades_by_window.items():
        model = models[label]
        spy_bars = _spy_bars(model)
        for tr in trades:
            d = tr["signal_date"]
            n += 1
            breadth = model._breadth.get(d)
            full = rc.regime_chop_from_spy_universe(spy_bars, d, breadth=breadth, index_agreement=_index_agreement(model, d))
            if full.get("regime_label") not in (None, "unknown"):
                full_label_pnls[full["regime_label"]].append(tr["pnl"])
                full_pchop_pnl.append((float(full["p_choppy_range"]), tr["pnl"]))
                exposure_by_label[full["regime_label"]].append(float(full["exposure_scalar"]))
            # THIN: production-context subset replayable from snapshot (trend+mom, no vix/breadth)
            idx = model._date_to_idx.get(d)
            feats = model._features_at_idx(idx) if idx is not None else None
            if feats is not None:
                thin = rc.regime_chop_from_features({"trend_pct_from_ma": feats["spy_trend_vs_sma200"], "ret20": feats["spy_ret20"]})
                if thin.get("regime_label") != "unknown":
                    thin_pchop_pnl.append((float(thin["p_choppy_range"]), tr["pnl"]))
    return {
        "total_trades": n,
        "full_overall_by_regime": {rl: _summ(full_label_pnls.get(rl, [])) for rl in rc.REGIME_LABELS},
        "full_spearman_pchop_vs_pnl": _spearman([s for s, _ in full_pchop_pnl], [p for _, p in full_pchop_pnl]),
        "thin_spearman_pchop_vs_pnl": _spearman([s for s, _ in thin_pchop_pnl], [p for _, p in thin_pchop_pnl]),
        "mean_exposure_scalar_by_regime": {rl: _round(sum(v) / len(v), 4) if v else None for rl, v in exposure_by_label.items()},
    }


def _build_payload() -> dict[str, Any]:
    models = _models()
    fgrs = base019._load_window_trades(base019.FGRS_SOURCE_ARTIFACT, ("pnl_without_low_liability_support", "pnl"))
    deferred = base019._load_window_trades(base019.DEFERRED_REVENUE_ARTIFACT, ("pnl", "paper_pnl"))
    fgrs_attr = _attribute(fgrs, models)
    deferred_attr = _attribute(deferred, models)

    fa = fgrs_attr["full_overall_by_regime"]
    chop_reproduced = bool(
        fa["choppy_range"]["count"] >= 10
        and fa["choppy_range"]["mean_pnl"] is not None
        and fa["risk_on_trend"]["mean_pnl"] is not None
        and fa["choppy_range"]["mean_pnl"] < 0
        and fa["risk_on_trend"]["mean_pnl"] > 0
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": base019._utc_now(),
        "lane": "measurement_repair",
        "status": "observed_only",
        "decision": "shared_regime_chop_helper_reproduces_lead" if chop_reproduced else "shared_regime_chop_helper_did_not_reproduce_lead",
        "accepted": False,
        "change_type": "identity_or_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": "shared_pit_regime_chop_state_helper",
        "rule_version": rc.RULE_VERSION,
        "builds_on": ["exp-20260615-019", "exp-20260615-023"],
        "hypothesis": (
            "The shared quant/regime_chop_state module reproduces the exp-019 "
            "choppy_range loss separation at full fidelity; the continuous "
            "exposure_scalar softly down-tilts only the choppy regime."
        ),
        "shared_module": "quant/regime_chop_state.py",
        "shared_module_rule_version": rc.RULE_VERSION,
        "full_fidelity_reproduces_chop_separation": chop_reproduced,
        "attribution": {
            "fundamental_growth_rs_low_liability": fgrs_attr,
            "deferred_revenue_demand_acceleration_exp017": deferred_attr,
        },
        "fidelity_note": (
            "FULL uses trend+breadth+index-agreement+drawdown+vol (replay / any "
            "bar-having daily caller). THIN uses trend+20d momentum only (the "
            "production market-state context subset replayable from the canonical "
            "snapshots, minus VIX which they lack). Compare full vs thin Spearman "
            "to see whether breadth/stress are load-bearing for the daily field."
        ),
        "production_impact": {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "parity_test_added": True,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
            "uses_llm": False,
            "daily_market_state_field_added": "gated_on_full_fidelity_reproduction",
            "parity_note": (
                "If full fidelity reproduces the lead, regime_chop is added as an "
                "additive read-only field on build_market_state_snapshot (the "
                "snapshot is already diagnostic_only and changes no orders). Any "
                "execution use (portfolio capital tilt) still needs a separate "
                "Gate 1-4 plus forward / live-pilot validation."
            ),
        },
        "next_evidence_needed": (
            "Forward / live-pilot rows tagged with entry-time regime_chop and "
            "exposure_scalar. Do not tune the regime constants or exposure floor "
            "on the frozen windows."
        ),
        "related_files": [
            base019._repo_rel(Path(__file__)),
            "quant/regime_chop_state.py",
            "quant/test_regime_chop_state.py",
            "quant/market_state_analysis.py",
            base019._repo_rel(OUT_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    fa = payload["attribution"]["fundamental_growth_rs_low_liability"]
    da = payload["attribution"]["deferred_revenue_demand_acceleration_exp017"]
    lines = [
        f"# {EXPERIMENT_ID} Shared Regime-Chop Helper Promotion",
        "",
        f"Status: `{payload['status']}`  Decision: `{payload['decision']}`",
        f"Shared module: `quant/regime_chop_state.py` (`{payload['rule_version']}`)  Builds on: exp-019, exp-023",
        "",
        f"Full-fidelity reproduces chop separation: **{payload['full_fidelity_reproduces_chop_separation']}**",
        "",
        "## Fundamental Growth + RS (FULL fidelity, via shared module)",
        "",
        "| regime | trades | mean PnL | win rate | mean exposure_scalar |",
        "|---|---:|---:|---:|---:|",
    ]
    for rl in rc.REGIME_LABELS:
        s = fa["full_overall_by_regime"][rl]
        ex = fa["mean_exposure_scalar_by_regime"].get(rl)
        lines.append(f"| {rl} | {s['count']} | {s['mean_pnl']} | {s['win_rate']} | {ex} |")
    lines += [
        "",
        f"- FULL Spearman(p_choppy, PnL): `{fa['full_spearman_pchop_vs_pnl']}` (expect negative)",
        f"- THIN Spearman(p_choppy, PnL): `{fa['thin_spearman_pchop_vs_pnl']}` (trend+momentum only)",
        "",
        "## Deferred-revenue exp-017 (FULL fidelity)",
        "",
        "| regime | trades | mean PnL | win rate |",
        "|---|---:|---:|---:|",
    ]
    for rl in rc.REGIME_LABELS:
        s = da["full_overall_by_regime"][rl]
        lines.append(f"| {rl} | {s['count']} | {s['mean_pnl']} | {s['win_rate']} |")
    lines += [
        "",
        f"- FULL Spearman(p_choppy, PnL): `{da['full_spearman_pchop_vs_pnl']}`",
        f"- THIN Spearman(p_choppy, PnL): `{da['thin_spearman_pchop_vs_pnl']}`",
        "",
        payload["fidelity_note"],
        "",
        "No JavaScript was used.",
    ]
    return "\n".join(lines) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base019._write_json(OUT_JSON, payload)
    base019._write_json(LOG_JSON, payload)
    base019._write_text(CARD_MD, _build_card(payload))
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "measurement_repair",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": payload["rule_version"],
        "builds_on": payload["builds_on"],
        "hypothesis": payload["hypothesis"],
        "full_fidelity_reproduces_chop_separation": payload["full_fidelity_reproduces_chop_separation"],
        "production_impact": payload["production_impact"],
        "artifact": base019._repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }
    experiment_registry.append_log_entry(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": base019._repo_rel(OUT_JSON),
        "full_fidelity_reproduces_chop_separation": payload["full_fidelity_reproduces_chop_separation"],
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
    }
    base019._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "full_fidelity_reproduces_chop_separation": payload["full_fidelity_reproduces_chop_separation"],
        "fgrs": payload["attribution"]["fundamental_growth_rs_low_liability"],
        "deferred": payload["attribution"]["deferred_revenue_demand_acceleration_exp017"],
    }, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
