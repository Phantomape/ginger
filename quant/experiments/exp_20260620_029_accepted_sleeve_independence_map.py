"""exp-20260620-029: accepted-sleeve return-independence map (measurement_repair).

Diagnostic only. Operationalizes the exp-20260620-020/027 conclusion (the core
book is genuinely idiosyncratic-alpha-driven, so the lever is deploying more
INDEPENDENT alpha, not factor beta). The question: of the accepted
candidate-pool paper sleeves, which are diversifying independent bets worth
scaling, and which are redundant re-loads of the same idiosyncratic exposure?

Forward paper rows are essentially empty (only low_deployment_etf has >10 closed
rows), so this uses each sleeve's HISTORICAL REPLAY (`build_*_historical_trades`)
over the three canonical windows with `core_entries_by_date={}` (each sleeve's
intrinsic signal set, no core-overlap exclusion). For each sleeve we build a
daily return-contribution series over the full window calendar (0 on no-trade
days, sum of entry-date net_return_pct otherwise) and compute:

  * pairwise Pearson correlation of daily return streams (portfolio-diversification
    metric: low = independent);
  * pairwise (ticker, entry_date) Jaccard overlap and ticker-set Jaccard
    (direct redundancy);
  * each sleeve's standalone profile (trades, active days, mean/median net
    return, hit rate, total pnl).

Independence ranking = mean absolute correlation to the other sleeves (lower =
more diversifying). Changes no strategy behavior. No JavaScript is used.
"""

from __future__ import annotations

import inspect
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

import importlib  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260620-029"
STEM = "accepted_sleeve_independence_map"
OWNER = "sleeve-independence"
LANE = "measurement_repair"
CHANGED_VARIABLE = "accepted_sleeve_return_independence_map"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_029_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS_META = {
    "late_strong": ("2025-10-23", "2026-04-21", "data/ohlcv/ohlcv_snapshot_20251023_20260421.json"),
    "mid_weak": ("2025-04-23", "2025-10-22", "data/ohlcv/ohlcv_snapshot_20250423_20251022.json"),
    "old_thin": ("2024-10-02", "2025-04-22", "data/ohlcv/ohlcv_snapshot_20241002_20250422.json"),
}

# (module, build fn, short label)
SLEEVES = [
    ("narrow_range_compression_breakout_paper_sleeve", "build_narrow_range_compression_breakout_historical_trades", "compression"),
    ("distribution_day_absorption_leadership_paper_sleeve", "build_distribution_day_absorption_leadership_historical_trades", "distribution"),
    ("fiftytwo_week_high_proximity_paper_sleeve", "build_fiftytwo_week_high_proximity_historical_trades", "fiftytwo_wk_high"),
    ("industry_relative_laggard_repair_paper_sleeve", "build_industry_relative_laggard_repair_historical_trades", "laggard_repair"),
    ("industry_stable_core_flow_paper_sleeve", "build_industry_stable_core_flow_historical_trades", "industry_stable_flow"),
    ("rolling_corr_peer_shock_paper_sleeve", "build_rolling_corr_peer_shock_historical_trades", "peer_shock"),
    ("turn_of_month_liquid_leadership_paper_sleeve", "build_turn_of_month_liquid_leadership_historical_trades", "turn_of_month"),
    ("volatility_relief_stock_leadership_paper_sleeve", "build_volatility_relief_stock_leadership_historical_trades", "vol_relief"),
    ("revision_surprise_low_extension_paper_sleeve", "build_revision_surprise_low_extension_historical_trades", "revision_surprise"),
    ("sbc_burden_improvement_paper_sleeve", "build_sbc_burden_improvement_historical_trades", "sbc_burden"),
    ("supplier_financing_debt_relief_paper_sleeve", "build_supplier_financing_debt_relief_historical_trades", "supplier_financing"),
    ("companyfacts_peer_confirmed_filing_drift_paper_sleeve", "build_companyfacts_peer_confirmed_historical_trades", "peer_confirmed_drift"),
]


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


def _round(x: Any, n: int = 4) -> Any:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def _merge_ohlcv() -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    all_dates: set[str] = set()
    for _label, (start, end, snap_rel) in WINDOWS_META.items():
        snap = json.loads((REPO_ROOT / snap_rel).read_text(encoding="utf-8"))
        ohlcv = snap.get("ohlcv", snap)
        for tk, rows in ohlcv.items():
            d = merged.setdefault(tk, {})
            for r in rows:
                date = str(r["Date"])[:10]
                d[date] = r
                if start <= date <= end:
                    all_dates.add(date)
    merged_ohlcv = {tk: [v for _, v in sorted(d.items())] for tk, d in merged.items()}
    return merged_ohlcv, sorted(all_dates)


def _call_sleeve(mod_name: str, fn_name: str, kwarg_pool: dict[str, Any]):
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name)
    sig = inspect.signature(fn)
    accepted = {k: v for k, v in kwarg_pool.items() if k in sig.parameters}
    res = fn(**accepted)
    if isinstance(res, tuple):
        trades = res[0]
    elif isinstance(res, dict):  # e.g. volatility_relief returns {"trades": [...], ...}
        trades = res.get("trades")
    else:
        trades = res
    return list(trades or [])


def _trade_return(t: dict[str, Any]) -> float | None:
    for key in ("net_return_pct", "pnl_pct_net"):
        v = t.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    pnl = t.get("pnl")
    notional = t.get("notional_usd") or t.get("paper_notional_usd")
    if pnl is not None and notional:
        try:
            return float(pnl) / float(notional)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return None


def _series_and_profile(trades: list[dict[str, Any]], calendar: list[str]) -> tuple[np.ndarray, dict[str, Any], set, set]:
    idx = {d: i for i, d in enumerate(calendar)}
    vec = np.zeros(len(calendar), dtype=float)
    rets: list[float] = []
    pnl_total = 0.0
    td_pairs: set[tuple[str, str]] = set()
    tickers: set[str] = set()
    n_in_cal = 0
    for t in trades:
        ed = str(t.get("entry_date") or t.get("signal_date") or t.get("date") or "")[:10]
        r = _trade_return(t)
        tk = str(t.get("ticker") or "")
        if r is None:
            continue
        rets.append(r)
        pnl_total += float(t.get("pnl") or 0.0)
        if tk and ed:
            td_pairs.add((tk, ed))
            tickers.add(tk)
        if ed in idx:
            vec[idx[ed]] += r
            n_in_cal += 1
    arr = np.array(rets) if rets else np.array([])
    profile = {
        "n_trades": len(trades),
        "n_trades_with_return": len(rets),
        "n_in_calendar": n_in_cal,
        "n_unique_tickers": len(tickers),
        "active_days": int((vec != 0).sum()),
        "mean_net_return_pct": _round(float(arr.mean()) if arr.size else None, 5),
        "median_net_return_pct": _round(float(np.median(arr)) if arr.size else None, 5),
        "hit_rate": _round(float((arr > 0).mean()) if arr.size else None, 4),
        "total_pnl": _round(pnl_total, 2),
    }
    return vec, profile, td_pairs, tickers


def _corr(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size != b.size or a.size < 3:
        return None
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _jaccard(a: set, b: set) -> float | None:
    if not a and not b:
        return None
    u = len(a | b)
    return _round(len(a & b) / u, 4) if u else None


def run() -> dict[str, Any]:
    merged_ohlcv, calendar = _merge_ohlcv()
    windows = {k: {"start": v[0], "end": v[1]} for k, v in WINDOWS_META.items()}
    try:
        framework = importlib.import_module("exp_20260605_033_cross_section_pressure_resilience_candidate_pool")
        sector_entries = framework._load_sector_entries()
    except Exception:
        sector_entries = {}
    try:
        from fundamental_growth_rs_paper_sleeve import load_companyfacts_rows

        companyfacts_growth_rows = load_companyfacts_rows()
    except Exception:
        companyfacts_growth_rows = []
    kwarg_pool = {
        "ohlcv_by_ticker": merged_ohlcv,
        "core_entries_by_date": {},
        "windows": windows,
        "sector_entries": sector_entries,
        "calendar_dates": calendar,
        "dates": calendar,
        # canonical allocator input is the sector-entries dict, not a bare set;
        # turn_of_month / vol_relief call .get on it.
        "candidate_universe": sector_entries or {t: {} for t in merged_ohlcv},
        "companyfacts_growth_rows": companyfacts_growth_rows,
    }

    series: dict[str, np.ndarray] = {}
    profiles: dict[str, dict[str, Any]] = {}
    td_pairs: dict[str, set] = {}
    tickers: dict[str, set] = {}
    sleeve_status: dict[str, str] = {}

    for mod_name, fn_name, label in SLEEVES:
        try:
            trades = _call_sleeve(mod_name, fn_name, kwarg_pool)
        except Exception as exc:  # noqa: BLE001
            sleeve_status[label] = f"error:{type(exc).__name__}:{exc}"[:200]
            continue
        vec, prof, tdp, tks = _series_and_profile(trades, calendar)
        if prof["n_trades_with_return"] == 0:
            sleeve_status[label] = "no_trades"
            continue
        series[label] = vec
        profiles[label] = prof
        td_pairs[label] = tdp
        tickers[label] = tks
        sleeve_status[label] = "ok"

    labels = sorted(series)
    corr_matrix: dict[str, dict[str, Any]] = {}
    td_overlap: dict[str, dict[str, Any]] = {}
    ticker_overlap: dict[str, dict[str, Any]] = {}
    for a in labels:
        corr_matrix[a] = {}
        td_overlap[a] = {}
        ticker_overlap[a] = {}
        for b in labels:
            corr_matrix[a][b] = _round(_corr(series[a], series[b]), 3) if a != b else 1.0
            td_overlap[a][b] = _jaccard(td_pairs[a], td_pairs[b]) if a != b else 1.0
            ticker_overlap[a][b] = _jaccard(tickers[a], tickers[b]) if a != b else 1.0

    independence = []
    for a in labels:
        corrs = [abs(corr_matrix[a][b]) for b in labels if b != a and corr_matrix[a][b] is not None]
        tds = [td_overlap[a][b] for b in labels if b != a and td_overlap[a][b] is not None]
        independence.append(
            {
                "sleeve": a,
                "mean_abs_corr_to_others": _round(float(np.mean(corrs)) if corrs else None, 3),
                "max_abs_corr_to_others": _round(float(np.max(corrs)) if corrs else None, 3),
                "mean_ticker_date_overlap": _round(float(np.mean(tds)) if tds else None, 4),
                "n_trades": profiles[a]["n_trades_with_return"],
                "active_days": profiles[a]["active_days"],
                "mean_net_return_pct": profiles[a]["mean_net_return_pct"],
                "total_pnl": profiles[a]["total_pnl"],
            }
        )
    independence.sort(key=lambda r: (r["mean_abs_corr_to_others"] if r["mean_abs_corr_to_others"] is not None else 9))

    return {
        "calendar_days": len(calendar),
        "merged_ticker_count": len(merged_ohlcv),
        "sleeve_status": sleeve_status,
        "sleeve_profiles": profiles,
        "independence_ranking": independence,
        "correlation_matrix": corr_matrix,
        "ticker_date_overlap_jaccard": td_overlap,
        "ticker_overlap_jaccard": ticker_overlap,
    }


def _interpret(attr: dict[str, Any]) -> str:
    ranking = attr["independence_ranking"]
    if not ranking:
        return "No sleeve produced replay trades; independence map is empty."
    most_indep = ranking[:3]
    least_indep = ranking[-2:]
    mi = ", ".join(f"{r['sleeve']}({r['mean_abs_corr_to_others']})" for r in most_indep)
    li = ", ".join(f"{r['sleeve']}({r['mean_abs_corr_to_others']})" for r in least_indep)
    n_ok = sum(1 for v in attr["sleeve_status"].values() if v == "ok")
    return (
        f"{n_ok} accepted sleeves replayed over {attr['calendar_days']} trading days. "
        f"Most independent (lowest mean |corr| to others, best to scale): {mi}. "
        f"Most redundant (highest correlation): {li}. Full correlation and "
        f"(ticker,date) overlap matrices in the artifact."
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
        "decision": "measurement_repair_accepted_sleeve_independence_map_built",
        "accepted": False,
        "accepted_alpha": False,
        "diagnostic_only": True,
        "builds_on": "exp-20260620-020, exp-20260620-027",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Map the return-stream independence of accepted candidate-pool paper "
            "sleeves via historical replay to identify diversifying bets worth "
            "scaling versus redundant re-loads."
        ),
        "method": (
            "Each accepted sleeve's build_*_historical_trades replayed over the 3 "
            "canonical windows with core_entries_by_date={}; daily entry-date "
            "return-contribution series (0-filled), pairwise Pearson correlation "
            "+ (ticker,date)/ticker Jaccard overlap; independence = mean |corr| "
            "to other sleeves."
        ),
        "attribution": attribution,
        "interpretation": interpretation,
        "limitations": [
            "Historical replay with core_entries_by_date={}; the live core-overlap "
            "exclusion is OFF, so these are each sleeve's intrinsic signals, not "
            "post-allocator deployed trades.",
            "Sparse sleeves: entry-date 0-filled daily-return correlation is "
            "dominated by co-absence, compressing magnitudes; read it alongside "
            "the (ticker,date) Jaccard overlap.",
            "Replay uses the frozen-window snapshots; no forward rows. Sleeves "
            "that fire 0 times here contribute no independence evidence.",
            "core ~56-name universe; correlations are in-sample on the 3 frozen "
            "windows.",
        ],
        "next_evidence_needed": (
            "Scale the most-independent, positive-EV sleeves first (small MANUAL "
            "live pilot per the incremental-capital policy), and validate the "
            "chop-regime exposure tilt on the resulting forward state-tagged rows; "
            "deprioritize high-correlation redundant sleeves for incremental "
            "capital."
        ),
        "production_impact": {
            "diagnostic_only": True,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "trade_enabled": False,
            "parity_note": "Read-only replay attribution. No order/ranking/sizing/exit/Gate-4 change.",
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
    print(json.dumps({
        "interpretation": interpretation,
        "sleeve_status": attribution["sleeve_status"],
        "independence_ranking": attribution["independence_ranking"],
    }, indent=2))


def _write_card(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    lines = [
        f"# {EXPERIMENT_ID} Accepted-Sleeve Return-Independence Map",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{payload['decision']}`",
        "",
        "Diagnostic only. Builds on exp-20260620-020/027. No strategy behavior changed.",
        "",
        "## Question",
        "",
        "Of the accepted candidate-pool sleeves, which are **independent** "
        "diversifying bets worth scaling, and which are **redundant** re-loads of "
        "the same idiosyncratic exposure? (forward rows are empty, so this uses "
        "historical replay over the 3 canonical windows.)",
        "",
        f"Replayed over `{attr['calendar_days']}` trading days, `{attr['merged_ticker_count']}`-name universe.",
        "",
        "## Independence ranking (low mean |corr| = more diversifying)",
        "",
        "| Sleeve | mean |corr| | max |corr| | mean (tk,date) overlap | trades | active days | mean ret | total pnl |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in attr["independence_ranking"]:
        lines.append(
            "| {s} | {mc} | {xc} | {ov} | {n} | {ad} | {mr} | {pnl} |".format(
                s=r["sleeve"], mc=r["mean_abs_corr_to_others"], xc=r["max_abs_corr_to_others"],
                ov=r["mean_ticker_date_overlap"], n=r["n_trades"], ad=r["active_days"],
                mr=r["mean_net_return_pct"], pnl=r["total_pnl"],
            )
        )
    # skipped/empty sleeves
    skipped = {k: v for k, v in attr["sleeve_status"].items() if v != "ok"}
    if skipped:
        lines += ["", "## Sleeves with no replay trades / errors", ""]
        for k, v in skipped.items():
            lines.append(f"- `{k}`: {v}")
    lines += ["", "## Interpretation", "", payload["interpretation"], "", "No JavaScript was used.", ""]
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_log(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    ranking = attr["independence_ranking"]
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "builds_on": "exp-20260620-020, exp-20260620-027",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "n_sleeves_replayed": sum(1 for v in attr["sleeve_status"].values() if v == "ok"),
        "most_independent": [r["sleeve"] for r in ranking[:3]],
        "most_redundant": [r["sleeve"] for r in ranking[-2:]],
        "interpretation": payload["interpretation"],
        "production_impact": payload["production_impact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }
    # upsert by experiment_id so a re-run does not duplicate the line
    existing = []
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                existing.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                continue
            existing.append(line)
    existing.append(json.dumps(record, sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(existing) + "\n", encoding="utf-8")


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
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _persist(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    ranking = attr["independence_ranking"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "n_sleeves_replayed": sum(1 for v in attr["sleeve_status"].values() if v == "ok"),
        "most_independent": [r["sleeve"] for r in ranking[:3]],
        "most_redundant": [r["sleeve"] for r in ranking[-2:]],
        "interpretation": payload["interpretation"],
        "production_impact": payload["production_impact"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "accepted_sleeve_return_attribution",
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
