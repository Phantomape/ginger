"""exp-20260620-020: core-stack beta / alpha attribution (measurement_repair).

Diagnostic only. Changes no strategy behavior. The question is simple and
load-bearing for research allocation: of the accepted core stack's canonical
fixed-window EV/PnL, how much is borrowed market / style-factor BETA exposure
(replicable for free with SPY/QQQ/IWM) versus residual ALPHA (skill that
survives after the exposures are removed)?

Method: re-run the canonical core backtest in-process for the three fixed
windows (the saved result files strip the equity curve, so it must be recomputed
in memory), turn each daily mark-to-market equity curve into a daily return
series, and regress it on free benchmark daily returns from the SAME snapshot:

  market model : r_s = a + b_mkt * r_SPY
  multi-factor : r_s = a + b_mkt * r_SPY + b_grow * (r_QQQ - r_SPY)
                                          + b_size * (r_IWM - r_SPY)

`a` is the per-day Jensen alpha (annualized for reporting); the betas are the
realized portfolio exposures (including cash drag, since the book is not always
fully invested). MTUM/QUAL pure momentum/quality factor ETFs are NOT in the
warehouse, so this v1 uses QQQ-SPY (large-growth tilt) and IWM-SPY (size tilt)
as the available style proxies; ingesting MTUM/QUAL is the named follow-up.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _p in (str(QUANT_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backtester import BacktestEngine  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260620-020"
STEM = "core_stack_beta_alpha_attribution"
OWNER = "beta-attribution"
LANE = "measurement_repair"
CHANGED_VARIABLE = "core_stack_beta_alpha_attribution_surface"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

TRADING_DAYS = 252

WINDOWS = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
        "doc_ev": 5.1628,
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
        "doc_ev": 2.1402,
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
        "doc_ev": 0.5911,
    },
]

BENCH_TICKERS = ["SPY", "QQQ", "IWM"]


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
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def _round(x: Any, n: int = 6) -> Any:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def _get_universe() -> list[str]:
    try:
        from data_layer import get_universe

        return list(get_universe())
    except Exception:
        from filter import WATCHLIST

        return list(WATCHLIST)


def _bench_daily_returns(snapshot_path: Path) -> dict[str, dict[str, float]]:
    """date -> {ticker: daily simple return} for each benchmark ticker."""
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    ohlcv = snap.get("ohlcv", snap)
    out: dict[str, dict[str, float]] = {}
    for ticker in BENCH_TICKERS:
        series = ohlcv.get(ticker)
        if not series:
            continue
        rows = sorted(series, key=lambda r: str(r["Date"])[:10])
        prev = None
        for r in rows:
            date = str(r["Date"])[:10]
            close = float(r["Close"])
            if prev is not None and prev > 0:
                out.setdefault(date, {})[ticker] = close / prev - 1.0
            prev = close
    return out


def _strategy_daily_returns(equity_curve: list) -> dict[str, float]:
    """date -> strategy daily simple return from the mark-to-market equity curve."""
    out: dict[str, float] = {}
    prev = None
    for item in equity_curve:
        date = str(item[0])[:10]
        equity = float(item[1])
        if prev is not None and prev > 0:
            out[date] = equity / prev - 1.0
        prev = equity
    return out


def _ols(y: np.ndarray, X: np.ndarray) -> dict[str, Any]:
    """OLS with intercept already included in X. Returns coefs, se, t, R2."""
    n, k = X.shape
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(n - k, 1)
    sigma2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    cov = sigma2 * xtx_inv
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = np.where(se > 0, beta / se, np.nan)
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    return {
        "n": int(n),
        "beta": beta.tolist(),
        "se": se.tolist(),
        "tstat": [None if (t is None or np.isnan(t)) else float(t) for t in tstat],
        "r2": r2,
        "resid_std_daily": math.sqrt(sigma2),
    }


def _annualize_alpha(daily_alpha: float) -> float:
    return (1.0 + daily_alpha) ** TRADING_DAYS - 1.0


def _aligned_arrays(strat: dict[str, float], bench: dict[str, dict[str, float]]):
    dates = sorted(d for d in strat if d in bench and all(t in bench[d] for t in BENCH_TICKERS))
    if not dates:
        return None
    y = np.array([strat[d] for d in dates], dtype=float)
    spy = np.array([bench[d]["SPY"] for d in dates], dtype=float)
    qqq = np.array([bench[d]["QQQ"] for d in dates], dtype=float)
    iwm = np.array([bench[d]["IWM"] for d in dates], dtype=float)
    return dates, y, spy, qqq, iwm


def _attribution_for(y, spy, qqq, iwm) -> dict[str, Any]:
    n = len(y)
    ones = np.ones(n)
    # market model
    Xm = np.column_stack([ones, spy])
    capm = _ols(y, Xm)
    a_m = capm["beta"][0]
    b_mkt = capm["beta"][1]
    # multi-factor
    Xf = np.column_stack([ones, spy, qqq - spy, iwm - spy])
    multi = _ols(y, Xf)
    a_f = multi["beta"][0]

    mean_strat = float(y.mean())
    # market-model decomposition of mean daily return
    beta_contrib_capm = b_mkt * float(spy.mean())
    alpha_contrib_capm = a_m
    # multi-factor decomposition
    mf_beta = multi["beta"]
    factors_mean = np.array([float(spy.mean()), float((qqq - spy).mean()), float((iwm - spy).mean())])
    beta_contrib_mf = float(np.dot(mf_beta[1:], factors_mean))
    alpha_contrib_mf = mf_beta[0]

    def _frac(part, whole):
        return None if whole == 0 else _round(part / whole, 4)

    return {
        "n_days": n,
        "mean_strategy_daily_return": _round(mean_strat),
        "mean_spy_daily_return": _round(float(spy.mean())),
        "market_model": {
            "alpha_daily": _round(a_m),
            "alpha_annualized": _round(_annualize_alpha(a_m)),
            "alpha_tstat": _round(capm["tstat"][0], 3),
            "beta_market": _round(b_mkt),
            "beta_market_tstat": _round(capm["tstat"][1], 3),
            "r2": _round(capm["r2"], 4),
            "mean_daily_decomposition": {
                "alpha": _round(alpha_contrib_capm),
                "market_beta": _round(beta_contrib_capm),
                "alpha_share_of_mean": _frac(alpha_contrib_capm, mean_strat),
                "beta_share_of_mean": _frac(beta_contrib_capm, mean_strat),
            },
        },
        "multi_factor": {
            "alpha_daily": _round(a_f),
            "alpha_annualized": _round(_annualize_alpha(a_f)),
            "alpha_tstat": _round(multi["tstat"][0], 3),
            "beta_market_spy": _round(mf_beta[1]),
            "beta_growth_qqq_minus_spy": _round(mf_beta[2]),
            "beta_size_iwm_minus_spy": _round(mf_beta[3]),
            "beta_tstats": {
                "spy": _round(multi["tstat"][1], 3),
                "qqq_minus_spy": _round(multi["tstat"][2], 3),
                "iwm_minus_spy": _round(multi["tstat"][3], 3),
            },
            "r2": _round(multi["r2"], 4),
            "mean_daily_decomposition": {
                "alpha": _round(alpha_contrib_mf),
                "factor_beta": _round(beta_contrib_mf),
                "alpha_share_of_mean": _frac(alpha_contrib_mf, mean_strat),
                "beta_share_of_mean": _frac(beta_contrib_mf, mean_strat),
            },
        },
    }


def run() -> dict[str, Any]:
    universe = _get_universe()
    per_window: dict[str, Any] = {}
    pooled_y: list[float] = []
    pooled_spy: list[float] = []
    pooled_qqq: list[float] = []
    pooled_iwm: list[float] = []
    ev_match: list[dict[str, Any]] = []

    for w in WINDOWS:
        label = w["label"]
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
        if "error" in result:
            per_window[label] = {"error": result["error"]}
            continue
        ec = result.get("equity_curve") or []
        strat = _strategy_daily_returns(ec)
        bench = _bench_daily_returns(w["snapshot"])
        aligned = _aligned_arrays(strat, bench)
        ev_match.append(
            {
                "window": label,
                "ev_recomputed": _round(result.get("expected_value_score"), 4),
                "ev_documented": w["doc_ev"],
                "sharpe_daily": result.get("sharpe_daily"),
                "total_pnl": _round(result.get("total_pnl"), 2),
                "trade_count": result.get("trade_count"),
                "equity_curve_days": len(ec),
            }
        )
        if aligned is None:
            per_window[label] = {"error": "no_aligned_benchmark_dates"}
            continue
        dates, y, spy, qqq, iwm = aligned
        attr = _attribution_for(y, spy, qqq, iwm)
        attr["window"] = label
        attr["aligned_dates"] = {"first": dates[0], "last": dates[-1], "count": len(dates)}
        per_window[label] = attr
        pooled_y.extend(y.tolist())
        pooled_spy.extend(spy.tolist())
        pooled_qqq.extend(qqq.tolist())
        pooled_iwm.extend(iwm.tolist())

    pooled = None
    if pooled_y:
        pooled = _attribution_for(
            np.array(pooled_y), np.array(pooled_spy), np.array(pooled_qqq), np.array(pooled_iwm)
        )
        pooled["window"] = "pooled_all_three"

    return {
        "per_window": per_window,
        "pooled": pooled,
        "ev_sanity_check": ev_match,
    }


def _interpret(payload: dict[str, Any]) -> str:
    pooled = payload.get("pooled") or {}
    mm = pooled.get("market_model", {})
    mf = pooled.get("multi_factor", {})
    beta_share = (mm.get("mean_daily_decomposition") or {}).get("beta_share_of_mean")
    a_ann = mm.get("alpha_annualized")
    a_t = mm.get("alpha_tstat")
    b = mm.get("beta_market")
    return (
        "Pooled across the three canonical windows the core stack's realized "
        f"market beta is {b}, the market model explains R2={mm.get('r2')} of daily "
        f"variance, annualized Jensen alpha is {a_ann} (t={a_t}); the multi-factor "
        f"model (add QQQ-SPY growth, IWM-SPY size) leaves annualized alpha "
        f"{mf.get('alpha_annualized')} (t={mf.get('alpha_tstat')}). Market beta "
        f"explains {beta_share} of the mean daily return under the market model."
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    attribution = run()
    interpretation = _interpret(attribution)
    timestamp = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": LANE,
        "status": "measurement_repair_observed_only",
        "decision": "measurement_repair_core_stack_beta_alpha_attribution_surface_built",
        "accepted": False,
        "accepted_alpha": False,
        "diagnostic_only": True,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Decompose the accepted core stack's canonical fixed-window returns "
            "into market/style beta and residual alpha to quantify how much EV is "
            "borrowed exposure versus skill."
        ),
        "method": (
            "In-process re-run of the canonical core backtest per fixed window "
            "(saved files strip equity_curve), daily equity-curve returns "
            "regressed on free SPY/QQQ/IWM daily returns from the same snapshot; "
            "market model and 3-factor style model with realized betas including "
            "cash drag."
        ),
        "attribution": attribution,
        "interpretation": interpretation,
        "limitations": [
            "MTUM/QUAL pure momentum/quality factor ETFs are absent from the "
            "warehouse; QQQ-SPY and IWM-SPY are style proxies, not orthogonal "
            "factors, so growth/size loadings are correlated.",
            "Realized betas include cash drag (book is not always fully invested), "
            "which is the intended 'how much market exposure did the book carry' "
            "reading but is not a fully-invested beta.",
            "Three fixed windows (~120-130 trading days each) give limited daily "
            "sample; per-window alpha t-stats should be read as indicative.",
            "Equity-curve daily marks use snapshot closes; this is the core-only "
            "canonical book, no pilot sleeve.",
        ],
        "next_evidence_needed": (
            "Ingest MTUM/QUAL (and optionally USMV/VLUE) into the warehouse to "
            "split the style beta into orthogonal momentum/quality/size/value "
            "loadings; then validate whether the chop-regime exposure tilt "
            "(regime_chop_state_v1) raises residual alpha on forward state-tagged "
            "rows."
        ),
        "production_impact": {
            "diagnostic_only": True,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "alters_orders": False,
            "alters_sizing": False,
            "alters_ranking": False,
            "alters_exits": False,
            "trade_enabled": False,
            "parity_note": (
                "Read-only attribution. No production code, order path, ranking, "
                "sizing, exit, or watchlist behavior changed."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
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
    print(json.dumps({"interpretation": interpretation, "ev_sanity_check": attribution["ev_sanity_check"], "pooled_market_model": (attribution.get("pooled") or {}).get("market_model")}, indent=2))


def _write_card(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    lines = [
        f"# {EXPERIMENT_ID} Core-Stack Beta / Alpha Attribution",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "Diagnostic only. No strategy behavior changed.",
        "",
        "## Question",
        "",
        "How much of the accepted core stack's canonical EV/PnL is borrowed "
        "market/style **beta** (free to replicate with SPY/QQQ/IWM) versus "
        "residual **alpha** (skill that survives removing those exposures)?",
        "",
        "## Market-model attribution by window",
        "",
        "| Window | n | beta_mkt | alpha/yr | alpha t | R2 | beta share of mean ret |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    order = ["late_strong", "mid_weak", "old_thin"]
    for label in order:
        w = attr["per_window"].get(label, {})
        mm = w.get("market_model")
        if not mm:
            lines.append(f"| {label} | - | - | - | - | - | (no data) |")
            continue
        dec = mm.get("mean_daily_decomposition", {})
        lines.append(
            "| {l} | {n} | {b} | {a:.1%} | {t} | {r2} | {bs} |".format(
                l=label,
                n=w.get("n_days"),
                b=mm.get("beta_market"),
                a=(mm.get("alpha_annualized") or 0.0),
                t=mm.get("alpha_tstat"),
                r2=mm.get("r2"),
                bs=dec.get("beta_share_of_mean"),
            )
        )
    pooled = attr.get("pooled") or {}
    pmm = pooled.get("market_model", {})
    pmf = pooled.get("multi_factor", {})
    pdec = pmm.get("mean_daily_decomposition", {})
    lines += [
        "",
        "## Pooled (all three windows)",
        "",
        f"- Market beta: `{pmm.get('beta_market')}` (t=`{pmm.get('beta_market_tstat')}`), "
        f"R2 `{pmm.get('r2')}`",
        f"- Market-model annualized alpha: `{pmm.get('alpha_annualized')}` "
        f"(t=`{pmm.get('alpha_tstat')}`)",
        f"- Market beta explains `{pdec.get('beta_share_of_mean')}` of mean daily "
        f"return; alpha explains `{pdec.get('alpha_share_of_mean')}`",
        f"- Multi-factor: beta_SPY `{pmf.get('beta_market_spy')}`, "
        f"growth(QQQ-SPY) `{pmf.get('beta_growth_qqq_minus_spy')}`, "
        f"size(IWM-SPY) `{pmf.get('beta_size_iwm_minus_spy')}`; "
        f"residual annualized alpha `{pmf.get('alpha_annualized')}` "
        f"(t=`{pmf.get('alpha_tstat')}`), R2 `{pmf.get('r2')}`",
        "",
        "## EV sanity check (recomputed vs documented baseline)",
        "",
        "| Window | EV recomputed | EV documented |",
        "|---|---:|---:|",
    ]
    for row in attr["ev_sanity_check"]:
        lines.append(f"| {row['window']} | {row['ev_recomputed']} | {row['ev_documented']} |")
    lines += [
        "",
        "## Interpretation",
        "",
        payload["interpretation"],
        "",
        "No JavaScript was used.",
        "",
    ]
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_log(payload: dict[str, Any]) -> None:
    pooled = (payload["attribution"].get("pooled") or {}).get("market_model", {})
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "pooled_market_beta": pooled.get("beta_market"),
        "pooled_alpha_annualized": pooled.get("alpha_annualized"),
        "pooled_alpha_tstat": pooled.get("alpha_tstat"),
        "pooled_r2": pooled.get("r2"),
        "interpretation": payload["interpretation"],
        "production_impact": payload["production_impact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }
    line = json.dumps(record, sort_keys=True)
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


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
            _repo_rel(CARD_MD): _sha256(CARD_MD),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _persist(payload: dict[str, Any]) -> None:
    pooled = (payload["attribution"].get("pooled") or {}).get("market_model", {})
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "pooled_market_beta": pooled.get("beta_market"),
        "pooled_alpha_annualized": pooled.get("alpha_annualized"),
        "pooled_r2": pooled.get("r2"),
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
