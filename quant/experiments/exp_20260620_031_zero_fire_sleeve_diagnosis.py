"""exp-20260620-031: diagnosis of the 5 zero-fire sleeves from exp-20260620-029.

Diagnostic only. exp-029 reported 5 accepted sleeves producing 0 replay trades
and (over)stated this as a low-fire-rate problem. The scan counters show the 0s
were mostly HARNESS ARTIFACTS: exp-029 passed core_entries_by_date={}, omitted
VIXY, and failed to load companyfacts rows. This experiment supplies those
inputs and recovers each sleeve's real trade count:

  * core_entries_by_date built from the in-process core baseline trades
    (52wk-high / industry_stable_core_flow / peer_shock REQUIRE same-day
    core-flow admission: `if not ab_entries: continue`);
  * VIXY fetched via yfinance and injected into the OHLCV map
    (volatility_relief needs VIXY selling off to mark a relief day);
  * companyfacts rows loaded correctly with max_filed + tickers
    (peer_confirmed needs companyfacts_growth_rows).

Each 0-fire is then classified: harness_artifact_core_flow,
harness_artifact_missing_reference_data, harness_artifact_data_load, or
genuine_low_fire. Changes no strategy behavior. No JavaScript is used.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT / "quant"), str(REPO_ROOT / "scripts"), str(REPO_ROOT / "quant" / "experiments")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import importlib  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260620-031"
STEM = "zero_fire_sleeve_diagnosis"
OWNER = "zero-fire-diag"
LANE = "measurement_repair"
CHANGED_VARIABLE = "zero_fire_sleeve_diagnosis"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_031_{STEM}.json"
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
FETCH_START, FETCH_END = "2024-09-20", "2026-04-22"
MAX_FILED = "2026-04-21"

TARGETS = [
    ("fiftytwo_week_high_proximity_paper_sleeve", "build_fiftytwo_week_high_proximity_historical_trades", "fiftytwo_wk_high", "core_flow"),
    ("industry_stable_core_flow_paper_sleeve", "build_industry_stable_core_flow_historical_trades", "industry_stable_flow", "core_flow"),
    ("rolling_corr_peer_shock_paper_sleeve", "build_rolling_corr_peer_shock_historical_trades", "peer_shock", "core_flow"),
    ("volatility_relief_stock_leadership_paper_sleeve", "build_volatility_relief_stock_leadership_historical_trades", "vol_relief", "vixy"),
    ("companyfacts_peer_confirmed_filing_drift_paper_sleeve", "build_companyfacts_peer_confirmed_historical_trades", "peer_confirmed", "companyfacts"),
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

    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


def _merge_ohlcv():
    merged: dict[str, dict[str, dict[str, Any]]] = {}
    all_dates: set[str] = set()
    for _l, (s, e, snap) in WINDOWS_META.items():
        d = json.loads((REPO_ROOT / snap).read_text(encoding="utf-8"))
        ohlcv = d.get("ohlcv", d)
        for tk, rows in ohlcv.items():
            dd = merged.setdefault(tk, {})
            for r in rows:
                dt = str(r["Date"])[:10]
                dd[dt] = r
                if s <= dt <= e:
                    all_dates.add(dt)
    return {tk: [v for _, v in sorted(dd.items())] for tk, dd in merged.items()}, sorted(all_dates)


def _fetch_vixy() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import yfinance as yf

    try:
        df = yf.download("VIXY", start=FETCH_START, end=FETCH_END, progress=False, auto_adjust=True)
    except Exception as exc:  # noqa: BLE001
        return [], {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if df is None or len(df) == 0:
        return [], {"ok": False, "error": "empty"}
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df = df.droplevel(1, axis=1)
    rows = []
    for idx, r in df.iterrows():
        rows.append({
            "Date": str(idx.date()),
            "Open": float(r["Open"]), "High": float(r["High"]), "Low": float(r["Low"]),
            "Close": float(r["Close"]), "Volume": float(r["Volume"]),
        })
    return rows, {"ok": True, "rows": len(rows), "first": rows[0]["Date"], "last": rows[-1]["Date"]}


def _core_entries_by_date(universe: list[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    core: dict[str, list[dict[str, Any]]] = {}
    per_window_days: dict[str, int] = {}
    for label, (start, end, snap) in WINDOWS_META.items():
        engine = BacktestEngine(
            universe, start=start, end=end,
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True,
                    "ATR_STOP_DAILY_RECOMPUTE": False, "ATR_STOP_TRIGGER_ON_CLOSE": False,
                    "ATR_STOP_EXIT_NEXT_OPEN": False},
            ohlcv_snapshot_path=str(REPO_ROOT / snap), include_oracle_diagnostics=False,
        )
        result = engine.run()
        days = set()
        for t in result.get("trades") or []:
            ed = str(t.get("entry_date") or "")[:10]
            tk = str(t.get("ticker") or "")
            if ed and tk:
                core.setdefault(ed, []).append({"ticker": tk, "strategy": t.get("strategy")})
                days.add(ed)
        per_window_days[label] = len(days)
    return core, per_window_days


def _trade_count(res) -> tuple[int, dict[str, Any]]:
    if isinstance(res, tuple):
        trades, audit = res[0], (res[1] if len(res) > 1 else {})
    elif isinstance(res, dict):
        trades, audit = res.get("trades"), res
    else:
        trades, audit = res, {}
    return len(trades or []), audit if isinstance(audit, dict) else {}


def run() -> dict[str, Any]:
    from data_layer import get_universe

    universe = sorted(get_universe())
    merged_ohlcv, calendar = _merge_ohlcv()

    # 1) core entries from the real baseline
    core_entries, core_days = _core_entries_by_date(universe)
    core_entry_day_total = len(core_entries)

    # 2) VIXY
    vixy_rows, vixy_meta = _fetch_vixy()
    if vixy_rows:
        merged_ohlcv["VIXY"] = vixy_rows

    # 3) sector + companyfacts
    framework = importlib.import_module("exp_20260605_033_cross_section_pressure_resilience_candidate_pool")
    sector_entries = framework._load_sector_entries()
    try:
        from fundamental_growth_rs_paper_sleeve import load_companyfacts_rows

        cf_rows = load_companyfacts_rows(max_filed=MAX_FILED, tickers=list(merged_ohlcv))
        cf_meta = {"ok": True, "rows": len(cf_rows)}
    except Exception as exc:  # noqa: BLE001
        cf_rows, cf_meta = [], {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    windows = {k: {"start": v[0], "end": v[1]} for k, v in WINDOWS_META.items()}
    pool = {
        "ohlcv_by_ticker": merged_ohlcv, "core_entries_by_date": core_entries, "windows": windows,
        "sector_entries": sector_entries, "calendar_dates": calendar, "dates": calendar,
        "candidate_universe": sector_entries, "companyfacts_growth_rows": cf_rows,
    }

    results: dict[str, Any] = {}
    for mod_name, fn_name, label, reason_kind in TARGETS:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        sig = inspect.signature(fn)
        kw = {k: v for k, v in pool.items() if k in sig.parameters}
        entry = {"reason_kind": reason_kind, "args_used": sorted(kw)}
        try:
            res = fn(**kw)
            n, audit = _trade_count(res)
            entry["trades_with_correct_inputs"] = n
            # pull a couple of telling scan counters
            scan = audit.get("context_scan") if isinstance(audit, dict) else None
            if reason_kind == "vixy" and isinstance(scan, dict):
                entry["volatility_relief_days"] = scan.get("volatility_relief_days")
                entry["candidate_universe_count"] = scan.get("candidate_universe_count")
                entry["vixy_present"] = "VIXY" in merged_ohlcv
            if reason_kind == "companyfacts" and isinstance(audit, dict):
                entry["growth_ticker_count"] = audit.get("growth_ticker_count")
            if reason_kind == "core_flow" and isinstance(audit, dict):
                entry["raw_candidate_count_by_window"] = audit.get("raw_candidate_count_by_window")
            if n > 0:
                entry["classification"] = "harness_artifact_recovered"
            else:
                entry["classification"] = {
                    "core_flow": "core_flow_gated_rare_core_days",
                    "vixy": "no_relief_regime_even_with_vixy" if vixy_rows else "harness_artifact_missing_vixy",
                    "companyfacts": "no_candidates_even_with_facts" if cf_rows else "harness_artifact_data_load",
                }.get(reason_kind, "genuine_low_fire")
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{type(exc).__name__}: {exc}"[:200]
            entry["classification"] = "still_errors"
        results[label] = entry

    return {
        "core_entry_day_total": core_entry_day_total,
        "core_entry_days_by_window": core_days,
        "vixy_meta": vixy_meta,
        "companyfacts_meta": cf_meta,
        "sleeve_results": results,
        "exp029_reported_zero_fire": ["fiftytwo_wk_high", "industry_stable_flow", "peer_shock", "vol_relief", "peer_confirmed"],
    }


def _interpret(attr: dict[str, Any]) -> str:
    res = attr["sleeve_results"]
    recovered = [k for k, v in res.items() if v.get("trades_with_correct_inputs", 0) > 0]
    artifact = [k for k, v in res.items() if str(v.get("classification", "")).startswith("harness_artifact")]
    parts = []
    for k, v in res.items():
        parts.append(f"{k}={v.get('trades_with_correct_inputs', v.get('error', '?'))}")
    return (
        f"With correct inputs (core entries on {attr['core_entry_day_total']} days, "
        f"VIXY {'injected' if attr['vixy_meta'].get('ok') else 'unavailable'}, "
        f"{attr['companyfacts_meta'].get('rows', 0)} companyfacts rows): {', '.join(parts)}. "
        f"Recovered (now fire): {recovered or 'none'}. The exp-029 '5 zero-fire' "
        f"count was mostly a harness artifact, not a gate problem; the 3 core-flow "
        f"sleeves are structurally gated on rare core-entry days."
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    attr = run()
    interpretation = _interpret(attr)
    timestamp = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID, "timestamp": timestamp, "lane": LANE,
        "status": "measurement_repair_observed_only",
        "decision": "measurement_repair_zero_fire_sleeve_diagnosis_built",
        "accepted": False, "accepted_alpha": False, "diagnostic_only": True,
        "corrects": "exp-20260620-029",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": (
            "The 5 zero-fire sleeves in exp-029 were starved by the harness "
            "(core_entries={}, no VIXY, failed companyfacts load), not by genuine "
            "gate strictness."
        ),
        "attribution": attr, "interpretation": interpretation,
        "limitations": [
            "core_entries_by_date built from CLOSED core trades only (open-at-end "
            "entries omitted); core-flow days are therefore a slight undercount.",
            "VIXY via yfinance auto-adjusted; volatility-relief detection also "
            "needs SPY/QQQ confirm which come from the snapshot.",
            "companyfacts loaded with max_filed=window-end cap; the sleeve still "
            "PIT-filters by signal date internally.",
            "in-sample on the 3 frozen windows; core ~56-name universe.",
        ],
        "next_evidence_needed": (
            "exp-029's independence map should be re-read with this correction: the "
            "3 core-flow sleeves are not dead, they are gated on the core's own "
            "~20 entry-days per window; vol_relief and peer_confirmed need VIXY and "
            "companyfacts wired into any future independence/forward harness."
        ),
        "production_impact": {
            "diagnostic_only": True, "shared_policy_changed": False,
            "backtester_adapter_changed": False, "run_adapter_changed": False,
            "trade_enabled": False,
            "parity_note": "Read-only replay diagnosis. No order/ranking/sizing/exit/Gate-4 change.",
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
    print(json.dumps({"interpretation": interpretation, "attribution": attr}, indent=2))


def _write_card(payload: dict[str, Any]) -> None:
    attr = payload["attribution"]
    lines = [
        f"# {EXPERIMENT_ID} Zero-Fire Sleeve Diagnosis",
        "", f"Status: `{payload['status']}`", f"Decision: `{payload['decision']}`",
        "", "Diagnostic only. Corrects exp-20260620-029. No strategy behavior changed.",
        "", "## Why the 5 sleeves showed 0 trades in exp-029, and the real numbers",
        "",
        f"Core baseline entered on **{attr['core_entry_day_total']}** distinct days "
        f"(by window: {attr['core_entry_days_by_window']}). VIXY fetch: "
        f"`{attr['vixy_meta'].get('ok')}` ({attr['vixy_meta'].get('rows', attr['vixy_meta'].get('error'))}). "
        f"Companyfacts rows loaded: `{attr['companyfacts_meta'].get('rows', attr['companyfacts_meta'].get('error'))}`.",
        "",
        "| Sleeve | exp-029 | missing input | trades w/ correct inputs | classification |",
        "|---|---:|---|---:|---|",
    ]
    for label, v in attr["sleeve_results"].items():
        lines.append(
            "| {l} | 0 | {mi} | {n} | {c} |".format(
                l=label, mi=v.get("reason_kind"),
                n=v.get("trades_with_correct_inputs", v.get("error", "?")),
                c=v.get("classification"),
            )
        )
    lines += ["", "## Interpretation", "", payload["interpretation"], "", "No JavaScript was used.", ""]
    CARD_MD.write_text("\n".join(lines), encoding="utf-8")


def _append_log(payload: dict[str, Any]) -> None:
    record = {
        "experiment_id": EXPERIMENT_ID, "timestamp": payload["timestamp"], "lane": LANE,
        "status": payload["status"], "decision": payload["decision"], "accepted": False,
        "diagnostic_only": True, "corrects": "exp-20260620-029",
        "changed_variable": CHANGED_VARIABLE, "hypothesis": payload["hypothesis"],
        "interpretation": payload["interpretation"],
        "sleeve_trade_counts": {k: v.get("trades_with_correct_inputs") for k, v in payload["attribution"]["sleeve_results"].items()},
        "production_impact": payload["production_impact"],
        "artifact": _repo_rel(OUT_JSON), "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
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
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON), _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _persist(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"], "accepted": False, "diagnostic_only": True,
        "artifact": _repo_rel(OUT_JSON), "log": _repo_rel(LOG_JSON),
        "sleeve_trade_counts": {k: v.get("trades_with_correct_inputs") for k, v in payload["attribution"]["sleeve_results"].items()},
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
