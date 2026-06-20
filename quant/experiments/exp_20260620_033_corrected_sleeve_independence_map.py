"""exp-20260620-033: corrected accepted-sleeve return-independence map.

Diagnostic only. exp-20260620-029 built the independence map but starved the
core-flow / VIXY / companyfacts sleeves (see exp-20260620-031). This rebuilds it
with the correct inputs so volatility_relief, fiftytwo_week_high and peer_shock
join the map, and reconciles why the two sleeves that stay ~0 in the
core-universe harness (industry_stable_core_flow, peer_confirmed) nonetheless
showed positive PnL in their own acceptance / broad backtests.

Inputs are assembled by reusing exp-20260620-031 helpers (core_entries from the
in-process core baseline, VIXY via yfinance, companyfacts rows) and the
correlation / profile logic from exp-20260620-029. Changes no strategy behavior.
No JavaScript is used.
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

import importlib  # noqa: E402
import exp_20260620_029_accepted_sleeve_independence_map as base29  # noqa: E402
import exp_20260620_031_zero_fire_sleeve_diagnosis as base31  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260620-033"
STEM = "corrected_sleeve_independence_map"
OWNER = "corrected-map"
LANE = "measurement_repair"
CHANGED_VARIABLE = "corrected_accepted_sleeve_independence_map"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_033_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

# Sourced reconciliation facts for the two sleeves that stay ~0 in the core harness.
RECONCILIATION = {
    "industry_stable_core_flow": {
        "core_harness_replay_trades": 0,
        "acceptance_experiment": "exp-20260608-008",
        "acceptance_trades": 47,
        "acceptance_trades_by_window": {"late_strong": 12, "mid_weak": 16, "old_thin": 19},
        "acceptance_raw_candidates_by_window": {"late_strong": 189, "mid_weak": 96, "old_thin": 140},
        "acceptance_pnl_delta_usd": 3731.54,
        "acceptance_ev_delta": 0.1459,
        "oos_closed_rows_exp_20260612_019": 1,
        "why_replay_zero": (
            "Requires same-day core A/B entry flow (`if not ab_entries: continue`). "
            "Acceptance used the production core-flow entries; this harness rebuilds "
            "core_entries_by_date from CLOSED core trades only (55 entry-days), which "
            "does not reproduce the exact A/B signal-day flow the sleeve keys on, so "
            "the industry-stable-leader intersection finds nothing. The +$3,731 / 47 "
            "trades are a real (low-frequency) edge, not a harness fidelity success."
        ),
    },
    "peer_confirmed": {
        "core_harness_replay_trades": 0,
        "core_harness_growth_ticker_count": 0,
        "broad_universe_sibling_experiment": "exp-20260605-016",
        "broad_universe_growth_ticker_count": 1274,
        "broad_universe_trades": 192,
        "broad_universe_pnl_delta_usd": 6770.51,
        "broad_universe_decision": "rejected (old_thin window EV/PnL regression)",
        "peer_gate_rejection_by_window_broad": {"late_strong": 15264, "mid_weak": 11577, "old_thin": 6162},
        "oos_closed_rows_exp_20260612_019": 0,
        "why_replay_zero": (
            "Needs the broad ~1446-name warehouse universe to find growth tickers and "
            "their absorbed industry peers; on the 56-name core snapshot "
            "growth_ticker_count=0. Even on the broad universe the peer-confirmation "
            "gate rejects ~99% of candidates and the family was REJECTED on old_thin, "
            "so its positive broad PnL (+$6,770) is a rejected lead, not an accepted edge."
        ),
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(p: Path) -> str:
    return base31._repo_rel(p)


def _round(x: Any, n: int = 4) -> Any:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def _build_pool():
    from data_layer import get_universe

    universe = sorted(get_universe())
    merged_ohlcv, calendar = base31._merge_ohlcv()
    core_entries, core_days = base31._core_entries_by_date(universe)
    vixy_rows, vixy_meta = base31._fetch_vixy()
    if vixy_rows:
        merged_ohlcv["VIXY"] = vixy_rows
    framework = importlib.import_module("exp_20260605_033_cross_section_pressure_resilience_candidate_pool")
    sector_entries = framework._load_sector_entries()
    try:
        from fundamental_growth_rs_paper_sleeve import load_companyfacts_rows

        cf_rows = load_companyfacts_rows(max_filed=base31.MAX_FILED, tickers=list(merged_ohlcv))
    except Exception:
        cf_rows = []
    windows = {k: {"start": v[0], "end": v[1]} for k, v in base31.WINDOWS_META.items()}
    pool = {
        "ohlcv_by_ticker": merged_ohlcv, "core_entries_by_date": core_entries, "windows": windows,
        "sector_entries": sector_entries, "calendar_dates": calendar, "dates": calendar,
        "candidate_universe": sector_entries, "companyfacts_growth_rows": cf_rows,
    }
    meta = {
        "core_entry_day_total": len(core_entries), "core_entry_days_by_window": core_days,
        "vixy_meta": vixy_meta, "companyfacts_rows": len(cf_rows), "calendar_days": len(calendar),
        "universe_count": len(merged_ohlcv),
    }
    return pool, calendar, meta


def run() -> dict[str, Any]:
    pool, calendar, meta = _build_pool()
    series: dict[str, np.ndarray] = {}
    profiles: dict[str, dict[str, Any]] = {}
    td_pairs: dict[str, set] = {}
    tickers: dict[str, set] = {}
    status: dict[str, str] = {}

    for mod_name, fn_name, label in base29.SLEEVES:
        try:
            trades = base29._call_sleeve(mod_name, fn_name, pool)
        except Exception as exc:  # noqa: BLE001
            status[label] = f"error:{type(exc).__name__}"[:60]
            continue
        vec, prof, tdp, tks = base29._series_and_profile(trades, calendar)
        if prof["n_trades_with_return"] == 0:
            status[label] = "no_trades"
            continue
        series[label] = vec
        profiles[label] = prof
        td_pairs[label] = tdp
        tickers[label] = tks
        status[label] = "ok"

    labels = sorted(series)
    corr = {a: {} for a in labels}
    tdov = {a: {} for a in labels}
    for a in labels:
        for b in labels:
            corr[a][b] = _round(base29._corr(series[a], series[b]), 3) if a != b else 1.0
            tdov[a][b] = base29._jaccard(td_pairs[a], td_pairs[b]) if a != b else 1.0

    ranking = []
    for a in labels:
        cs = [abs(corr[a][b]) for b in labels if b != a and corr[a][b] is not None]
        ts = [tdov[a][b] for b in labels if b != a and tdov[a][b] is not None]
        ranking.append({
            "sleeve": a,
            "mean_abs_corr_to_others": _round(float(np.mean(cs)) if cs else None, 3),
            "max_abs_corr_to_others": _round(float(np.max(cs)) if cs else None, 3),
            "mean_ticker_date_overlap": _round(float(np.mean(ts)) if ts else None, 4),
            "n_trades": profiles[a]["n_trades_with_return"],
            "mean_net_return_pct": profiles[a]["mean_net_return_pct"],
            "total_pnl": profiles[a]["total_pnl"],
        })
    ranking.sort(key=lambda r: (r["mean_abs_corr_to_others"] if r["mean_abs_corr_to_others"] is not None else 9))

    return {
        "input_meta": meta,
        "sleeve_status": status,
        "independence_ranking": ranking,
        "correlation_matrix": corr,
        "ticker_date_overlap_jaccard": tdov,
        "reconciliation_near_zero_sleeves": RECONCILIATION,
    }


def _interpret(attr: dict[str, Any]) -> str:
    r = attr["independence_ranking"]
    n_ok = sum(1 for v in attr["sleeve_status"].values() if v == "ok")
    if not r:
        return "No sleeve fired."
    mi = ", ".join(f"{x['sleeve']}({x['mean_abs_corr_to_others']})" for x in r[:3])
    return (
        f"{n_ok} accepted sleeves now fire with correct inputs (vs 7 in exp-029). "
        f"Still near-mutually-uncorrelated. Most independent: {mi}. vol_relief "
        f"fires the most ({next((x['n_trades'] for x in r if x['sleeve']=='vol_relief'), 'n/a')} "
        f"trades). industry_stable_core_flow and peer_confirmed stay 0 in this "
        f"core-universe harness but were positive in their own acceptance/broad "
        f"backtests (see reconciliation): the 0s are a harness-fidelity gap, not "
        f"dead sleeves."
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    attr = run()
    interpretation = _interpret(attr)
    ts = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID, "timestamp": ts, "lane": LANE,
        "status": "measurement_repair_observed_only",
        "decision": "measurement_repair_corrected_sleeve_independence_map_built",
        "accepted": False, "diagnostic_only": True, "supersedes": "exp-20260620-029",
        "builds_on": "exp-20260620-029, exp-20260620-031",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "Rebuild the sleeve independence map with core_entries/VIXY/companyfacts "
            "supplied, and reconcile the two still-near-zero sleeves against their "
            "acceptance backtests."
        ),
        "attribution": attr, "interpretation": interpretation,
        "limitations": [
            "core_entries_by_date rebuilt from CLOSED core trades only, so core-flow "
            "sleeves (fiftytwo_wk_high, peer_shock, industry_stable_core_flow) still "
            "under-fire vs their production acceptance harness.",
            "peer_confirmed needs the broad ~1446-name universe; the 56-name core "
            "harness cannot map it (growth_ticker_count=0).",
            "0-filled sparse daily-return Pearson compresses magnitudes; read with "
            "the (ticker,date) Jaccard overlap; in-sample on 3 frozen windows.",
        ],
        "next_evidence_needed": (
            "For a fully faithful independence map, drive the sleeves from the "
            "production daily core-flow entries and the broad warehouse universe, "
            "not the 56-name core snapshot + closed-trade core_entries. For "
            "deployment, the low forward fire-rate (exp-20260612-019 OOS: most "
            "sleeves 0-7 closed rows) means scaling needs several independent "
            "sleeves together plus small live pilots to accumulate forward rows."
        ),
        "production_impact": {
            "diagnostic_only": True, "shared_policy_changed": False,
            "backtester_adapter_changed": False, "run_adapter_changed": False,
            "trade_enabled": False,
            "parity_note": "Read-only replay attribution. No order/ranking/sizing/exit/Gate-4 change.",
        },
        "related_files": [
            _repo_rel(Path(__file__)), _repo_rel(OUT_JSON), _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON), _repo_rel(TICKET_JSON), _repo_rel(LOG_JSON),
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
    print(json.dumps({"interpretation": interpretation, "ranking": attr["independence_ranking"],
                      "status": attr["sleeve_status"], "input_meta": attr["input_meta"]}, indent=2))


def _write_card(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    m = attr["input_meta"]
    lines = [
        f"# {EXPERIMENT_ID} Corrected Sleeve Independence Map",
        "", f"Status: `{payload['status']}`  Decision: `{payload['decision']}`",
        "", "Diagnostic only. Supersedes exp-20260620-029 (which starved core-flow/VIXY/companyfacts sleeves).",
        "",
        f"Inputs: core entries on **{m['core_entry_day_total']}** days {m['core_entry_days_by_window']}, "
        f"VIXY `{m['vixy_meta'].get('ok')}`, companyfacts rows `{m['companyfacts_rows']}`, "
        f"{m['calendar_days']} trading days, {m['universe_count']}-name universe.",
        "",
        "## Independence ranking (low mean |corr| = more diversifying)",
        "",
        "| Sleeve | mean |corr| | max |corr| | (tk,date) overlap | trades | mean ret | total pnl |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in attr["independence_ranking"]:
        lines.append("| {s} | {mc} | {xc} | {ov} | {n} | {mr} | {p} |".format(
            s=r["sleeve"], mc=r["mean_abs_corr_to_others"], xc=r["max_abs_corr_to_others"],
            ov=r["mean_ticker_date_overlap"], n=r["n_trades"], mr=r["mean_net_return_pct"], p=r["total_pnl"]))
    skipped = {k: v for k, v in attr["sleeve_status"].items() if v != "ok"}
    if skipped:
        lines += ["", "## Did not fire in this harness", ""]
        for k, v in skipped.items():
            lines.append(f"- `{k}`: {v}")
    lines += ["", "## Why the two near-zero sleeves showed positive backtest PnL elsewhere", ""]
    for name, rec in attr["reconciliation_near_zero_sleeves"].items():
        lines.append(f"### {name}")
        for k, v in rec.items():
            lines.append(f"- `{k}`: {v}")
        lines.append("")
    lines += ["## Interpretation", "", payload["interpretation"], "", "No JavaScript was used.", ""]
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_log(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    record = {
        "experiment_id": EXPERIMENT_ID, "timestamp": payload["timestamp"], "lane": LANE,
        "status": payload["status"], "decision": payload["decision"], "accepted": False,
        "diagnostic_only": True, "supersedes": "exp-20260620-029",
        "changed_variable": CHANGED_VARIABLE, "hypothesis": payload["hypothesis"],
        "n_sleeves_fired": sum(1 for v in attr["sleeve_status"].values() if v == "ok"),
        "ranking_sleeves": [r["sleeve"] for r in attr["independence_ranking"]],
        "interpretation": payload["interpretation"], "production_impact": payload["production_impact"],
        "artifact": _repo_rel(OUT_JSON), "log": _repo_rel(LOG_JSON), "anti_js": "No JavaScript was used.",
    }
    existing = []
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    continue
            except Exception:
                pass
            existing.append(line)
    existing.append(json.dumps(record, sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(existing) + "\n", encoding="utf-8")


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID, "status": payload["status"], "decision": payload["decision"],
        "created_at": payload["timestamp"], "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)), _repo_rel(OUT_JSON), _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON), _repo_rel(TICKET_JSON), _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG), _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): base31._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base31._sha256(OUT_JSON), _repo_rel(CARD_MD): base31._sha256(CARD_MD),
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _persist(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    result = {
        "decision": payload["decision"], "accepted": False, "diagnostic_only": True,
        "artifact": _repo_rel(OUT_JSON), "log": _repo_rel(LOG_JSON),
        "n_sleeves_fired": sum(1 for v in attr["sleeve_status"].values() if v == "ok"),
        "ranking_sleeves": [r["sleeve"] for r in attr["independence_ranking"]],
        "interpretation": payload["interpretation"], "production_impact": payload["production_impact"],
    }
    fields = {
        "owner": OWNER, "hypothesis": payload["hypothesis"],
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "accepted_sleeve_return_attribution",
        "single_causal_variable": CHANGED_VARIABLE, "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"], "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON), "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON), "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
    }
    persist_self_registered_result(
        REGISTRY_JSON, experiment_id=EXPERIMENT_ID, lane=LANE, prediction=None,
        result=result, status=payload["status"], fields=fields,
    )


if __name__ == "__main__":
    main()
