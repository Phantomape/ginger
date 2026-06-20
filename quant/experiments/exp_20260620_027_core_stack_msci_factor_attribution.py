"""exp-20260620-027: core-stack MSCI single-factor attribution (measurement_repair).

Diagnostic only. Upgrades exp-20260620-020 (which could only use SPY/QQQ/IWM) to
an orthogonal-ish MSCI single-factor decomposition. The load-bearing question:
of the +2.1 annualized "alpha" exp-020 found after removing market/QQQ/IWM, how
much is actually a MOMENTUM (or quality) factor loading versus true residual
skill?

Method:
  * Fetch the iShares MSCI USA single-factor ETFs (MTUM momentum, QUAL quality,
    VLUE value, USMV min-vol, SIZE size) plus SPY via yfinance (auto-adjusted),
    save to a sidecar, turn into daily returns.
  * Re-run the canonical core backtest in-process for the three fixed windows
    (saved files strip equity_curve) and turn each daily equity curve into a
    daily return series (reusing exp-20260620-020 helpers).
  * Regress strategy daily returns on:
      market model : r_s = a + b_mkt * r_SPY                        (reproduce)
      momentum-only: r_s = a + b_mkt * r_SPY + b_mom*(MTUM - SPY)
      full factor  : r_s = a + b_mkt*r_SPY + sum_f b_f*(ETF_f - SPY)
    where ETF_f - SPY is each factor ETF's excess-over-market (a long-short
    factor-mimicking proxy). The intercept `a` is residual alpha after the
    factors; comparing it to the market-model alpha shows how much momentum /
    quality absorbed.

This changes no strategy behavior. MTUM/QUAL/VLUE/USMV/SIZE were also added to
ohlcv_warehouse DEFAULT_REFERENCE_TICKERS (reference/context only, never traded)
so daily runs warehouse them going forward. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT / "quant"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "quant" / "experiments")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exp_20260620_020_core_stack_beta_alpha_attribution as base20  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260620-027"
STEM = "core_stack_msci_factor_attribution"
OWNER = "factor-attribution"
LANE = "measurement_repair"
CHANGED_VARIABLE = "core_stack_msci_factor_attribution_surface"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_027_{STEM}.json"
SIDECAR_JSON = OUT_DIR / "factor_etf_daily.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

TRADING_DAYS = base20.TRADING_DAYS
WINDOWS = base20.WINDOWS
MARKET = "SPY"
FACTOR_ETFS = ["MTUM", "QUAL", "VLUE", "USMV", "SIZE"]
FACTOR_LABEL = {
    "MTUM": "momentum",
    "QUAL": "quality",
    "VLUE": "value",
    "USMV": "min_vol",
    "SIZE": "size",
}
FETCH_START = "2024-09-20"
FETCH_END = "2026-04-22"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return str(path)


def _sha256(path: Path) -> str | None:
    import hashlib

    if not Path(path).exists():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _round(x: Any, n: int = 6) -> Any:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def _fetch_factor_closes() -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    """ticker -> {date: adjusted_close} for SPY + factor ETFs, via yfinance."""
    import yfinance as yf

    tickers = [MARKET] + FACTOR_ETFS
    closes: dict[str, dict[str, float]] = {}
    meta: dict[str, Any] = {}
    for t in tickers:
        try:
            df = yf.download(t, start=FETCH_START, end=FETCH_END, progress=False, auto_adjust=True)
        except Exception as exc:  # noqa: BLE001
            meta[t] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            continue
        if df is None or len(df) == 0:
            meta[t] = {"ok": False, "error": "empty"}
            continue
        col = df["Close"]
        if hasattr(col, "columns"):  # multiindex single-ticker frame
            col = col.iloc[:, 0]
        series = {str(idx.date()): float(val) for idx, val in col.items() if val == val}
        closes[t] = series
        meta[t] = {"ok": True, "rows": len(series), "first": min(series), "last": max(series)}
    return closes, meta


def _daily_returns(closes: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    prev = None
    for date in sorted(closes):
        c = closes[date]
        if prev is not None and prev > 0:
            out[date] = c / prev - 1.0
        prev = c
    return out


def _run_strategy_returns() -> dict[str, dict[str, float]]:
    """window label -> {date: strategy daily return} plus EV sanity."""
    universe = base20._get_universe()
    out: dict[str, dict[str, float]] = {}
    ev_check = []
    for w in WINDOWS:
        engine = BacktestEngine(
            universe,
            start=w["start"],
            end=w["end"],
            config={
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "ATR_STOP_DAILY_RECOMPUTE": False,
                "ATR_STOP_TRIGGER_ON_CLOSE": False,
                "ATR_STOP_EXIT_NEXT_OPEN": False,
            },
            ohlcv_snapshot_path=str(w["snapshot"]),
            include_oracle_diagnostics=False,
        )
        result = engine.run()
        ec = result.get("equity_curve") or []
        out[w["label"]] = base20._strategy_daily_returns(ec)
        ev_check.append(
            {
                "window": w["label"],
                "ev_recomputed": _round(result.get("expected_value_score"), 4),
                "ev_documented": w["doc_ev"],
            }
        )
    out["_ev_check"] = ev_check  # type: ignore[assignment]
    return out


def _regress_block(
    strat: dict[str, float],
    fret: dict[str, dict[str, float]],
    available_factors: list[str],
) -> dict[str, Any] | None:
    dates = sorted(
        d
        for d in strat
        if d in fret[MARKET] and all(d in fret[f] for f in available_factors)
    )
    if len(dates) < 10:
        return None
    y = np.array([strat[d] for d in dates], dtype=float)
    mkt = np.array([fret[MARKET][d] for d in dates], dtype=float)
    factor_cols = {f: np.array([fret[f][d] - fret[MARKET][d] for d in dates], dtype=float) for f in available_factors}
    n = len(y)
    ones = np.ones(n)

    # market model
    capm = base20._ols(y, np.column_stack([ones, mkt]))
    # momentum-only (if MTUM present)
    mom = None
    if "MTUM" in available_factors:
        mom = base20._ols(y, np.column_stack([ones, mkt, factor_cols["MTUM"]]))
    # full factor model
    Xf = np.column_stack([ones, mkt] + [factor_cols[f] for f in available_factors])
    full = base20._ols(y, Xf)

    def pack_factor(model, names):
        coefs = model["beta"]
        ts = model["tstat"]
        out = {"alpha_daily": _round(coefs[0]), "alpha_annualized": _round(base20._annualize_alpha(coefs[0])),
               "alpha_tstat": _round(ts[0], 3), "beta_market": _round(coefs[1]), "r2": _round(model["r2"], 4),
               "n": model["n"], "loadings": {}}
        for i, fac in enumerate(names):
            out["loadings"][FACTOR_LABEL[fac]] = {"beta": _round(coefs[2 + i]), "tstat": _round(ts[2 + i], 3)}
        return out

    block = {
        "n_days": n,
        "dates": {"first": dates[0], "last": dates[-1]},
        "market_model": {
            "alpha_daily": _round(capm["beta"][0]),
            "alpha_annualized": _round(base20._annualize_alpha(capm["beta"][0])),
            "alpha_tstat": _round(capm["tstat"][0], 3),
            "beta_market": _round(capm["beta"][1]),
            "r2": _round(capm["r2"], 4),
        },
        "full_factor_model": pack_factor(full, available_factors),
    }
    if mom is not None:
        block["momentum_only_model"] = {
            "alpha_daily": _round(mom["beta"][0]),
            "alpha_annualized": _round(base20._annualize_alpha(mom["beta"][0])),
            "alpha_tstat": _round(mom["tstat"][0], 3),
            "beta_market": _round(mom["beta"][1]),
            "beta_momentum": _round(mom["beta"][2]),
            "beta_momentum_tstat": _round(mom["tstat"][2], 3),
            "r2": _round(mom["r2"], 4),
        }
    # how much the factors absorbed vs the market-model alpha
    capm_alpha_ann = base20._annualize_alpha(capm["beta"][0])
    full_alpha_ann = base20._annualize_alpha(full["beta"][0])
    block["alpha_absorbed_by_factors_annualized"] = _round(capm_alpha_ann - full_alpha_ann)
    return block


def run() -> dict[str, Any]:
    closes, fetch_meta = _fetch_factor_closes()
    available_factors = [f for f in FACTOR_ETFS if f in closes]
    SIDECAR_JSON.parent.mkdir(parents=True, exist_ok=True)
    SIDECAR_JSON.write_text(json.dumps({"closes": closes, "fetch_meta": fetch_meta}, indent=2, sort_keys=True), encoding="utf-8")

    fret = {t: _daily_returns(c) for t, c in closes.items()}
    if MARKET not in fret:
        return {"error": "spy_fetch_failed", "fetch_meta": fetch_meta}

    strat_all = _run_strategy_returns()
    ev_check = strat_all.pop("_ev_check")

    per_window: dict[str, Any] = {}
    pooled_strat: dict[str, float] = {}
    for label, strat in strat_all.items():
        blk = _regress_block(strat, fret, available_factors)
        if blk is not None:
            blk["window"] = label
        per_window[label] = blk
        # for pooling, prefix dates with window to keep them unique while aligning to same fret keys
        pooled_strat.update(strat)

    pooled = _regress_block(pooled_strat, fret, available_factors)
    if pooled is not None:
        pooled["window"] = "pooled_all_three"

    return {
        "available_factors": available_factors,
        "factor_labels": {f: FACTOR_LABEL[f] for f in available_factors},
        "fetch_meta": fetch_meta,
        "ev_sanity_check": ev_check,
        "per_window": per_window,
        "pooled": pooled,
        "sidecar": _repo_rel(SIDECAR_JSON),
    }


def _interpret(attr: dict[str, Any]) -> str:
    pooled = attr.get("pooled") or {}
    mm = pooled.get("market_model", {})
    full = pooled.get("full_factor_model", {})
    mom = pooled.get("momentum_only_model", {})
    loads = full.get("loadings", {})
    mom_load = loads.get("momentum", {})
    qual_load = loads.get("quality", {})
    return (
        "Pooled across the three windows: exp-020 market-model annualized alpha "
        f"{mm.get('alpha_annualized')} (t={mm.get('alpha_tstat')}). Adding the MSCI "
        f"factor ETFs, momentum loading (MTUM-SPY) is {mom_load.get('beta')} "
        f"(t={mom_load.get('tstat')}), quality loading {qual_load.get('beta')} "
        f"(t={qual_load.get('tstat')}); full-factor residual annualized alpha is "
        f"{full.get('alpha_annualized')} (t={full.get('alpha_tstat')}), R2 "
        f"{full.get('r2')}. Factors absorbed "
        f"{pooled.get('alpha_absorbed_by_factors_annualized')} of annualized alpha. "
        f"Momentum-only model leaves alpha {mom.get('alpha_annualized') if mom else 'n/a'}."
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    attribution = run()
    if attribution.get("error"):
        print(json.dumps(attribution, indent=2))
        raise SystemExit("factor fetch failed: " + str(attribution.get("error")))
    interpretation = _interpret(attribution)
    timestamp = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": LANE,
        "status": "measurement_repair_observed_only",
        "decision": "measurement_repair_core_stack_msci_factor_attribution_surface_built",
        "accepted": False,
        "accepted_alpha": False,
        "diagnostic_only": True,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Decompose the core stack's daily returns on MSCI single-factor ETFs "
            "(momentum/quality/value/min-vol/size) to measure how much of the "
            "exp-020 residual alpha is a momentum/quality factor loading versus "
            "true residual skill."
        ),
        "builds_on": "exp-20260620-020",
        "method": (
            "yfinance auto-adjusted SPY+MTUM+QUAL+VLUE+USMV+SIZE daily returns vs "
            "in-process core backtest daily equity-curve returns over the three "
            "canonical windows; market / momentum-only / full-factor OLS with "
            "factor-ETF-minus-SPY excess-return regressors."
        ),
        "attribution": attribution,
        "interpretation": interpretation,
        "limitations": [
            "Factor-ETF-minus-SPY excess returns are correlated, not orthogonal "
            "factors; multicollinearity inflates individual loading standard "
            "errors (read the joint R2 and the momentum-only model alongside the "
            "full model).",
            "yfinance auto-adjusted closes for the factor ETFs vs snapshot-based "
            "strategy equity marks; small source/adjustment differences possible.",
            "Realized betas include cash drag; three windows ~120-130 days each.",
        ],
        "next_evidence_needed": (
            "If a momentum loading absorbs most of the alpha, treat the core book "
            "as a momentum-factor vehicle and prioritize independent (low "
            "momentum-correlation) alpha sleeves; if residual alpha survives the "
            "factors, the selection edge is genuine and the lever is capacity / "
            "deployment. Then validate the chop-regime exposure tilt on forward "
            "state-tagged rows."
        ),
        "production_impact": {
            "diagnostic_only": True,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "reference_universe_changed": True,
            "reference_universe_note": (
                "Added MTUM/QUAL/VLUE/USMV/SIZE to ohlcv_warehouse "
                "DEFAULT_REFERENCE_TICKERS (reference/context only, never traded; "
                "tagged seeded_local_reference, excluded from the candidate "
                "universe). No order, ranking, sizing, exit, or Gate-4 metric "
                "changes."
            ),
            "trade_enabled": False,
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(SIDECAR_JSON),
            _repo_rel(REPO_ROOT / "quant" / "ohlcv_warehouse.py"),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_card(payload)
    _append_log(payload)
    _write_manifest(payload)
    _persist(payload)
    print(json.dumps({
        "interpretation": interpretation,
        "ev_sanity_check": attribution["ev_sanity_check"],
        "available_factors": attribution["available_factors"],
        "pooled": attribution.get("pooled"),
    }, indent=2))


def _write_card(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    pooled = attr.get("pooled") or {}
    mm = pooled.get("market_model", {})
    full = pooled.get("full_factor_model", {})
    mom = pooled.get("momentum_only_model", {})
    loads = full.get("loadings", {})
    lines = [
        f"# {EXPERIMENT_ID} Core-Stack MSCI Factor Attribution",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "Diagnostic only. Builds on exp-20260620-020. No strategy behavior changed.",
        "",
        "## Question",
        "",
        "Of the +2.1 annualized residual alpha exp-020 found after SPY/QQQ/IWM, how "
        "much is actually a **momentum / quality factor loading** versus true "
        "residual skill?",
        "",
        f"Available factor ETFs: `{', '.join(attr['available_factors'])}`",
        "",
        "## Pooled (all three windows)",
        "",
        f"- exp-020 market-model annualized alpha: `{mm.get('alpha_annualized')}` (t=`{mm.get('alpha_tstat')}`), beta_mkt `{mm.get('beta_market')}`, R2 `{mm.get('r2')}`",
    ]
    if mom:
        lines.append(
            f"- Momentum-only model: momentum beta `{mom.get('beta_momentum')}` (t=`{mom.get('beta_momentum_tstat')}`), residual alpha `{mom.get('alpha_annualized')}` (t=`{mom.get('alpha_tstat')}`), R2 `{mom.get('r2')}`"
        )
    lines.append(
        f"- Full-factor residual annualized alpha: `{full.get('alpha_annualized')}` (t=`{full.get('alpha_tstat')}`), R2 `{full.get('r2')}`"
    )
    lines.append(f"- Annualized alpha absorbed by factors: `{pooled.get('alpha_absorbed_by_factors_annualized')}`")
    lines.append("")
    lines.append("### Full-model factor loadings (ETF − SPY excess)")
    lines.append("")
    lines.append("| Factor | beta | t |")
    lines.append("|---|---:|---:|")
    for fac, v in loads.items():
        lines.append(f"| {fac} | {v.get('beta')} | {v.get('tstat')} |")
    lines += [
        "",
        "## Per-window full-factor residual alpha",
        "",
        "| Window | n | mkt beta | momentum beta | resid alpha/yr | resid alpha t | R2 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ["late_strong", "mid_weak", "old_thin"]:
        w = attr["per_window"].get(label)
        if not w:
            lines.append(f"| {label} | (no data) | | | | | |")
            continue
        f = w.get("full_factor_model", {})
        ld = f.get("loadings", {})
        lines.append(
            "| {l} | {n} | {b} | {m} | {a} | {t} | {r2} |".format(
                l=label, n=f.get("n"), b=f.get("beta_market"),
                m=(ld.get("momentum") or {}).get("beta"),
                a=f.get("alpha_annualized"), t=f.get("alpha_tstat"), r2=f.get("r2"),
            )
        )
    lines += [
        "",
        "## EV sanity check",
        "",
        "| Window | EV recomputed | EV documented |",
        "|---|---:|---:|",
    ]
    for row in attr["ev_sanity_check"]:
        lines.append(f"| {row['window']} | {row['ev_recomputed']} | {row['ev_documented']} |")
    lines += ["", "## Interpretation", "", payload["interpretation"], "", "No JavaScript was used.", ""]
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_log(payload: dict[str, Any]) -> None:
    pooled = payload["attribution"].get("pooled") or {}
    full = pooled.get("full_factor_model", {})
    mm = pooled.get("market_model", {})
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "builds_on": "exp-20260620-020",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "pooled_market_model_alpha_annualized": mm.get("alpha_annualized"),
        "pooled_full_factor_alpha_annualized": full.get("alpha_annualized"),
        "pooled_full_factor_alpha_tstat": full.get("alpha_tstat"),
        "pooled_momentum_loading": (full.get("loadings", {}).get("momentum") or {}).get("beta"),
        "alpha_absorbed_by_factors_annualized": pooled.get("alpha_absorbed_by_factors_annualized"),
        "interpretation": payload["interpretation"],
        "production_impact": payload["production_impact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(SIDECAR_JSON),
            _repo_rel(REPO_ROOT / "quant" / "ohlcv_warehouse.py"),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(SIDECAR_JSON): _sha256(SIDECAR_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _persist(payload: dict[str, Any]) -> None:
    pooled = payload["attribution"].get("pooled") or {}
    full = pooled.get("full_factor_model", {})
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "pooled_full_factor_alpha_annualized": full.get("alpha_annualized"),
        "pooled_momentum_loading": (full.get("loadings", {}).get("momentum") or {}).get("beta"),
        "alpha_absorbed_by_factors_annualized": pooled.get("alpha_absorbed_by_factors_annualized"),
        "interpretation": payload["interpretation"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "core_stack_return_attribution",
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=None,
        result=result,
        status=payload["status"],
        fields=fields,
    )


if __name__ == "__main__":
    main()
