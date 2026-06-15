"""exp-20260615-028: full-fidelity daily regime_chop context plumbing.

Adds the regime_chop STRESS axis (SPY drawdown-from-252d-high + 20d-vol-ratio)
and optional breadth to `build_readonly_market_state_context`, so the daily
production `regime_chop` field is no longer the thin trend+momentum+VIX subset.
SPY drawdown/vol come from the SPY frame the daily path already supplies, so they
reach production with NO run.py change. Breadth needs the universe frames passed
at the run.py call site; that one-line wiring is deferred behind exp-20260607-003's
active run.py claim and is the remaining step.

This runner quantifies the upgrade: it re-runs the exp-20260615-025 chop
attribution at three fidelities and reports Spearman(p_choppy, PnL), showing the
now-production-reachable stress-only tier is materially closer to full fidelity
than the thin tier was. Read-only; no orders, ranking, sizing, or exits change.
No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import experiment_registry  # noqa: E402
import exp_20260615_019_pit_regime_state_attribution as base019  # noqa: E402
import regime_chop_state as rc  # noqa: E402

EXPERIMENT_ID = "exp-20260615-028"
STEM = "regime_chop_full_fidelity_context"
CHANGED_VARIABLE = "full_fidelity_daily_regime_chop_context_plumbing"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_028_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = base019.WINDOWS
_spearman = base019._spearman


def _models() -> dict[str, base019.RegimeModel]:
    models = {}
    for label, (_s, _e, path) in WINDOWS.items():
        ohlcv = json.loads((REPO_ROOT / path).read_text(encoding="utf-8")).get("ohlcv") or {}
        models[label] = base019.RegimeModel(ohlcv)
    return models


def _idx_agree(model: base019.RegimeModel, date: str) -> float:
    hits = sum(1 for t in base019.INDEX_TICKERS if model._idx_ret20.get(t, {}).get(date, 0.0) > 0)
    return hits / len(base019.INDEX_TICKERS)


def _fidelity_spearmans(trades_by_window: dict[str, list[dict[str, Any]]], models: dict[str, base019.RegimeModel]) -> dict[str, Any]:
    thin: list[tuple[float, float]] = []
    stress: list[tuple[float, float]] = []
    full: list[tuple[float, float]] = []
    for label, trades in trades_by_window.items():
        model = models[label]
        for tr in trades:
            d = tr["signal_date"]
            idx = model._date_to_idx.get(d)
            f = model._features_at_idx(idx) if idx is not None else None
            if f is None:
                continue
            trend = f["spy_trend_vs_sma200"]
            ret20 = f["spy_ret20"]
            dd = f["spy_drawdown_from_252d_high"]
            vr = f["spy_vol_ratio_vs_100d_median"]
            breadth = model._breadth.get(d)
            ia = _idx_agree(model, d)
            pnl = tr["pnl"]
            t = rc.regime_chop_from_features({"trend_pct_from_ma": trend, "ret20": ret20})
            s = rc.regime_chop_from_features({"trend_pct_from_ma": trend, "ret20": ret20, "drawdown_from_high": dd, "vol_ratio": vr})
            fu = rc.regime_chop_from_features({"trend_pct_from_ma": trend, "ret20": ret20, "drawdown_from_high": dd, "vol_ratio": vr, "breadth": breadth, "index_agreement": ia})
            if t.get("regime_label") != "unknown":
                thin.append((float(t["p_choppy_range"]), pnl))
            if s.get("regime_label") != "unknown":
                stress.append((float(s["p_choppy_range"]), pnl))
            if fu.get("regime_label") != "unknown":
                full.append((float(fu["p_choppy_range"]), pnl))
    return {
        "n": len(full),
        "thin_spearman_pchop_vs_pnl": _spearman([s for s, _ in thin], [p for _, p in thin]),
        "stress_only_spearman_pchop_vs_pnl": _spearman([s for s, _ in stress], [p for _, p in stress]),
        "full_spearman_pchop_vs_pnl": _spearman([s for s, _ in full], [p for _, p in full]),
    }


def _build_payload() -> dict[str, Any]:
    models = _models()
    fgrs = base019._load_window_trades(base019.FGRS_SOURCE_ARTIFACT, ("pnl_without_low_liability_support", "pnl"))
    deferred = base019._load_window_trades(base019.DEFERRED_REVENUE_ARTIFACT, ("pnl", "paper_pnl"))
    fgrs_fid = _fidelity_spearmans(fgrs, models)
    deferred_fid = _fidelity_spearmans(deferred, models)
    # production now reaches stress_only (drawdown/vol from SPY frame, no run.py change).
    upgrade = bool(
        fgrs_fid["stress_only_spearman_pchop_vs_pnl"] is not None
        and fgrs_fid["thin_spearman_pchop_vs_pnl"] is not None
        and fgrs_fid["stress_only_spearman_pchop_vs_pnl"] < fgrs_fid["thin_spearman_pchop_vs_pnl"]
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": base019._utc_now(),
        "lane": "measurement_repair",
        "status": "observed_only",
        "decision": "daily_regime_chop_stress_axis_plumbed_breadth_wiring_deferred",
        "accepted": False,
        "change_type": "identity_or_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": "full_fidelity_daily_regime_chop_context",
        "rule_version": rc.RULE_VERSION,
        "builds_on": ["exp-20260615-019", "exp-20260615-025"],
        "hypothesis": (
            "Adding SPY drawdown/vol (and optional breadth) to the daily "
            "market-state context lifts the production regime_chop field from the "
            "thin tier toward the full-fidelity construct exp-025 validated."
        ),
        "code_changes": {
            "quant/market_context.py": "added spy_drawdown_from_high, spy_vol_ratio, optional breadth",
            "quant/regime_chop_state.py": "thin adapter now consumes drawdown/vol/breadth and reports fidelity tier",
            "quant/run.py": "NOT changed (blocked by exp-20260607-003 run.py claim); breadth wiring deferred",
        },
        "production_fidelity_after_change": "stress_only_no_breadth",
        "stress_axis_upgrade_confirmed": upgrade,
        "fidelity_spearmans": {
            "fundamental_growth_rs_low_liability": fgrs_fid,
            "deferred_revenue_demand_acceleration_exp017": deferred_fid,
        },
        "production_impact": {
            "replay_only": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "daily_market_state_field_enriched": True,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_watchlist_changed": False,
            "uses_llm": False,
            "parity_note": (
                "build_readonly_market_state_context now emits spy_drawdown_from_high "
                "and spy_vol_ratio from the SPY frame it already receives; the daily "
                "regime_chop field upgrades from thin to stress_only with no run.py "
                "change. The field stays inside the diagnostic_only market-state "
                "snapshot and changes no orders. Breadth (full fidelity) needs the "
                "run.py call site to pass universe frames; deferred behind "
                "exp-20260607-003."
            ),
        },
        "next_evidence_needed": (
            "Once exp-20260607-003 releases run.py, pass universe_ohlcv_by_ticker to "
            "build_readonly_market_state_context for full-fidelity breadth. Then "
            "validate the exposure_scalar soft tilt on forward / live-pilot rows "
            "tagged with entry-time regime_chop. Do not tune constants on frozen windows."
        ),
        "related_files": [
            base019._repo_rel(Path(__file__)),
            "quant/market_context.py",
            "quant/regime_chop_state.py",
            "quant/test_market_context_regime_features.py",
            base019._repo_rel(OUT_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    fg = payload["fidelity_spearmans"]["fundamental_growth_rs_low_liability"]
    df = payload["fidelity_spearmans"]["deferred_revenue_demand_acceleration_exp017"]
    return "\n".join([
        f"# {EXPERIMENT_ID} Full-Fidelity Daily regime_chop Context",
        "",
        f"Status: `{payload['status']}`  Decision: `{payload['decision']}`",
        f"Production fidelity after change: **{payload['production_fidelity_after_change']}**  "
        f"(stress-axis upgrade confirmed: {payload['stress_axis_upgrade_confirmed']})",
        "",
        "## Spearman(p_choppy, PnL) by fidelity (more negative = cleaner chop separation)",
        "",
        "| trade set | thin | stress_only (now in prod) | full |",
        "|---|---:|---:|---:|",
        f"| Fundamental Growth + RS | {fg['thin_spearman_pchop_vs_pnl']} | {fg['stress_only_spearman_pchop_vs_pnl']} | {fg['full_spearman_pchop_vs_pnl']} |",
        f"| Deferred-revenue exp-017 | {df['thin_spearman_pchop_vs_pnl']} | {df['stress_only_spearman_pchop_vs_pnl']} | {df['full_spearman_pchop_vs_pnl']} |",
        "",
        "## Code changes",
        "",
        "- `quant/market_context.py`: added `spy_drawdown_from_high`, `spy_vol_ratio`, optional `breadth`.",
        "- `quant/regime_chop_state.py`: thin adapter consumes drawdown/vol/breadth + reports fidelity tier.",
        "- `quant/run.py`: NOT changed (blocked by exp-20260607-003); breadth wiring deferred.",
        "",
        "Read-only: the regime_chop field lives in the diagnostic_only market-state snapshot; no orders change.",
        "",
        "No JavaScript was used.",
    ]) + "\n"


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
        "builds_on": payload["builds_on"],
        "hypothesis": payload["hypothesis"],
        "production_fidelity_after_change": payload["production_fidelity_after_change"],
        "stress_axis_upgrade_confirmed": payload["stress_axis_upgrade_confirmed"],
        "fidelity_spearmans": payload["fidelity_spearmans"],
        "production_impact": payload["production_impact"],
        "artifact": base019._repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }
    experiment_registry.append_log_entry(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": base019._repo_rel(OUT_JSON),
        "production_fidelity_after_change": payload["production_fidelity_after_change"],
        "fidelity_spearmans": payload["fidelity_spearmans"],
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
    base019._write_json(MANIFEST_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
    })


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "production_fidelity_after_change": payload["production_fidelity_after_change"],
        "stress_axis_upgrade_confirmed": payload["stress_axis_upgrade_confirmed"],
        "fidelity_spearmans": payload["fidelity_spearmans"],
    }, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
