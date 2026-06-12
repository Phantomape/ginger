"""exp-20260612-019: post-acceptance OOS replay readiness surface (measurement repair).

Read-only audit. Accepted default-off paper sleeves have near-zero closed
forward rows because daily accumulation ran on a starved 27-57 name fallback
universe until the 2026-06-12 repairs. This runner replays the shared sleeve
helpers on the unified declared universe over 2026-04-22..2026-06-11, which is
strictly AFTER the frozen Gate-4 windows (out-of-sample for every accepted
adapter), attaches cost-adjusted replacement-value fields, and merges the rows
with genuine forward closed rows into a per-sleeve readiness report.

Boundary: replay rows are labeled evidence_class=post_acceptance_oos_replay and
are NEVER written into sleeve state/snapshots; genuine forward rows stay the
only forward evidence. This artifact informs activation gating; it does not
activate anything. No production behavior changes. No JavaScript is used.
"""

from __future__ import annotations

import inspect
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework

REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260612-019"
STEM = "post_acceptance_oos_replay_readiness"
CHANGED_VARIABLE = "post_acceptance_oos_replay_readiness_surface_v1"
OWNER = "claude-scheduled-alpha"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SLEEVE_DATA_DIR = REPO_ROOT / "data" / "paper_sleeves"
WAREHOUSE = framework.WAREHOUSE

OOS_CFG = {"start": "2026-04-22", "end": "2026-06-11"}
WINDOWS = {"post_acceptance_oos": OOS_CFG}
READINESS_MIN_COMBINED_CLOSED = 20

HELPERS = [
    ("accepted_helper_source_priority_allocator", "accepted_helper_source_priority_allocator_paper_sleeve", "build_accepted_helper_source_priority_allocator_historical_trades"),
    ("distribution_day_absorption_leadership", "distribution_day_absorption_leadership_paper_sleeve", "build_distribution_day_absorption_leadership_historical_trades"),
    ("fiftytwo_week_high_proximity", "fiftytwo_week_high_proximity_paper_sleeve", "build_fiftytwo_week_high_proximity_historical_trades"),
    ("industry_relative_laggard_repair", "industry_relative_laggard_repair_paper_sleeve", "build_industry_relative_laggard_repair_historical_trades"),
    ("industry_stable_core_flow", "industry_stable_core_flow_paper_sleeve", "build_industry_stable_core_flow_historical_trades"),
    ("narrow_range_compression_breakout", "narrow_range_compression_breakout_paper_sleeve", "build_narrow_range_compression_breakout_historical_trades"),
    ("revision_surprise_low_extension", "revision_surprise_low_extension_paper_sleeve", "build_revision_surprise_low_extension_historical_trades"),
    ("rolling_corr_peer_shock", "rolling_corr_peer_shock_paper_sleeve", "build_rolling_corr_peer_shock_historical_trades"),
    ("turn_of_month_liquid_leadership", "turn_of_month_liquid_leadership_paper_sleeve", "build_turn_of_month_liquid_leadership_historical_trades"),
    ("volatility_relief_leadership", "volatility_relief_stock_leadership_paper_sleeve", "build_volatility_relief_stock_leadership_historical_trades"),
    ("companyfacts_peer_confirmed_filing_drift", "companyfacts_peer_confirmed_filing_drift_paper_sleeve", "build_companyfacts_peer_confirmed_historical_trades"),
]


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _run_oos_baseline(universe: list[str]) -> dict[str, Any]:
    engine = framework.shadow.BacktestEngine(
        universe=universe,
        start=OOS_CFG["start"],
        end=OOS_CFG["end"],
        config=framework.shadow.BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_warehouse_path=str(WAREHOUSE),
    )
    return engine.run()


def _etf_leg_pnl(
    snapshot: dict[str, list[dict[str, Any]]],
    etf: str,
    entry_date: str,
    exit_date: str,
    notional: float,
) -> float | None:
    rows = framework.shadow._series(snapshot, etf)
    index = framework.shadow._row_index(rows)
    entry_idx = index.get(str(entry_date)[:10])
    exit_idx = index.get(str(exit_date)[:10])
    if entry_idx is None or exit_idx is None:
        return None
    entry_open = framework._value(rows[entry_idx], "Open")
    exit_close = framework._value(rows[exit_idx], "Close")
    if not entry_open or not exit_close:
        return None
    return notional * (float(exit_close) / float(entry_open) - 1.0)


def _attach_replacement_values(
    trades: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
) -> None:
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        notional = float(trade.get("paper_notional_usd") or trade.get("notional_usd") or 4000.0)
        entry_date = trade.get("entry_date")
        exit_date = trade.get("exit_date")
        spy = _etf_leg_pnl(snapshot, "SPY", entry_date, exit_date, notional)
        qqq = _etf_leg_pnl(snapshot, "QQQ", entry_date, exit_date, notional)
        trade["evidence_class"] = "post_acceptance_oos_replay"
        trade["replacement_value_vs_cash_usd"] = round(pnl, 2)
        trade["replacement_value_vs_spy_usd"] = round(pnl - spy, 2) if spy is not None else None
        trade["replacement_value_vs_qqq_usd"] = round(pnl - qqq, 2) if qqq is not None else None


def _genuine_forward_rows() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for state_path in sorted(SLEEVE_DATA_DIR.glob("*/state.json")):
        sleeve = state_path.parent.name
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        closed = state.get("closed_positions") or []
        dates = [str(t.get("entry_date") or "")[:10] for t in closed if t.get("entry_date")]
        out[sleeve] = {
            "forward_closed_count": len(closed),
            "forward_pnl_usd": round(sum(float(t.get("pnl_usd") or t.get("pnl") or 0.0) for t in closed), 2),
            "forward_rv_cash_usd": round(sum(float(t.get("replacement_value_vs_cash_usd") or 0.0) for t in closed), 2),
            "forward_rv_spy_usd": round(sum(float(t.get("replacement_value_vs_spy_usd") or 0.0) for t in closed), 2),
            "forward_first_entry": min(dates) if dates else None,
            "forward_last_entry": max(dates) if dates else None,
            "open_position_count": len(state.get("open_positions") or []),
            "pending_entry_count": len(state.get("pending_entries") or []),
        }
    return out


def _call_helper(
    module_name: str,
    function_name: str,
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    core_entries: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    window_dates: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    module = __import__(module_name)
    fn = getattr(module, function_name)
    superset = {
        "ohlcv_by_ticker": snapshot,
        "core_entries_by_date": core_entries,
        "windows": WINDOWS,
        "candidate_universe": sector_entries,
        "dates": window_dates,
        "sector_entries": sector_entries,
        "companyfacts_growth_rows": [],
    }
    accepted = inspect.signature(fn).parameters
    kwargs = {key: value for key, value in superset.items() if key in accepted}
    result = fn(**kwargs)
    if isinstance(result, tuple):
        trades, audit = result
    elif isinstance(result, dict):
        trades = result.get("trades") or []
        audit = {key: value for key, value in result.items() if key != "trades"}
    else:
        trades, audit = [], {}
    return list(trades or []), dict(audit or {})


def _summarise_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trades if t.get("exit_date")]
    pnl = sum(float(t.get("pnl") or 0.0) for t in closed)
    rv_spy_values = [t.get("replacement_value_vs_spy_usd") for t in closed]
    rv_spy = sum(float(v) for v in rv_spy_values if v is not None)
    rv_qqq = sum(float(t.get("replacement_value_vs_qqq_usd") or 0.0) for t in closed)
    by_ticker = Counter()
    for t in closed:
        by_ticker[str(t.get("ticker") or "")] += 1
    positive = [t for t in closed if float(t.get("pnl") or 0.0) > 0]
    pos_pnl = sum(float(t.get("pnl") or 0.0) for t in positive)
    top_share = None
    if pos_pnl > 0:
        by_ticker_pos = Counter()
        for t in positive:
            by_ticker_pos[str(t.get("ticker") or "")] += float(t.get("pnl") or 0.0)
        top_share = round(max(by_ticker_pos.values()) / pos_pnl, 4)
    wins = len(positive)
    return {
        "oos_closed_count": len(closed),
        "oos_pnl_usd": round(pnl, 2),
        "oos_rv_cash_usd": round(pnl, 2),
        "oos_rv_spy_usd": round(rv_spy, 2),
        "oos_rv_qqq_usd": round(rv_qqq, 2),
        "oos_win_rate": round(wins / len(closed), 4) if closed else None,
        "oos_unique_tickers": len(by_ticker),
        "oos_top_ticker_positive_pnl_share": top_share,
    }


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    sector_entries = framework._load_sector_entries()
    universe = sorted(framework.get_universe())
    print("[oos] core baseline 2026-04-22..2026-06-11 (warehouse mode)")
    baseline = _run_oos_baseline(universe)
    core_entries = framework.shadow._baseline_entries(baseline)
    print("[oos] loading unified-universe snapshot")
    snapshot = framework._load_window_snapshot(
        cfg=OOS_CFG,
        eligible_tickers=set(sector_entries),
    )
    window_dates = [
        d
        for d in framework.shadow._trading_dates(snapshot)
        if OOS_CFG["start"] <= d <= OOS_CFG["end"]
    ]
    forward_rows = _genuine_forward_rows()
    sleeves: dict[str, dict[str, Any]] = {}
    for sleeve_key, module_name, function_name in HELPERS:
        print(f"[oos] replay {sleeve_key}")
        entry: dict[str, Any] = {
            "sleeve_key": sleeve_key,
            "helper_module": module_name,
            "helper_function": function_name,
            "evidence_class": "post_acceptance_oos_replay",
        }
        try:
            trades, audit = _call_helper(
                module_name,
                function_name,
                snapshot=snapshot,
                core_entries=core_entries,
                sector_entries=sector_entries,
                window_dates=window_dates,
            )
            _attach_replacement_values(trades, snapshot)
            entry.update(_summarise_trades(trades))
            entry["replay_status"] = "ok"
            entry["helper_audit"] = framework._safe(audit)
            entry["oos_trades"] = framework._safe(trades)
        except Exception as error:  # noqa: BLE001
            entry["replay_status"] = "replay_unavailable"
            entry["replay_error"] = f"{type(error).__name__}: {error}"
            entry.update(_summarise_trades([]))
        sleeves[sleeve_key] = entry

    readiness: list[dict[str, Any]] = []
    forward_dir_by_key = {
        "accepted_helper_source_priority_allocator": "accepted_helper_source_priority_allocator",
        "distribution_day_absorption_leadership": "distribution_day_absorption_leadership",
        "industry_relative_laggard_repair": "industry_relative_laggard_repair",
        "industry_stable_core_flow": "industry_stable_core_flow",
        "narrow_range_compression_breakout": "narrow_range_compression_breakout",
        "revision_surprise_low_extension": "revision_surprise_low_extension",
        "rolling_corr_peer_shock": "rolling_corr_peer_shock",
        "turn_of_month_liquid_leadership": "turn_of_month_liquid_leadership",
        "volatility_relief_leadership": "volatility_relief_leadership",
    }
    for sleeve_key, entry in sleeves.items():
        fwd = forward_rows.get(forward_dir_by_key.get(sleeve_key, sleeve_key)) or {}
        combined = int(entry.get("oos_closed_count") or 0) + int(fwd.get("forward_closed_count") or 0)
        rv_cash = float(entry.get("oos_rv_cash_usd") or 0.0) + float(fwd.get("forward_rv_cash_usd") or 0.0)
        rv_spy = float(entry.get("oos_rv_spy_usd") or 0.0) + float(fwd.get("forward_rv_spy_usd") or 0.0)
        if entry.get("replay_status") != "ok":
            bucket = "replay_unavailable_continue_forward_accumulation"
        elif combined >= READINESS_MIN_COMBINED_CLOSED and rv_cash > 0 and rv_spy > 0:
            bucket = "activation_gate_candidate"
        else:
            bucket = "continue_accumulation"
        readiness.append({
            "sleeve_key": sleeve_key,
            "readiness_bucket": bucket,
            "combined_closed_count": combined,
            "combined_rv_cash_usd": round(rv_cash, 2),
            "combined_rv_spy_usd": round(rv_spy, 2),
            "oos_closed_count": entry.get("oos_closed_count"),
            "oos_rv_spy_usd": entry.get("oos_rv_spy_usd"),
            "oos_top_ticker_positive_pnl_share": entry.get("oos_top_ticker_positive_pnl_share"),
            "forward_closed_count": fwd.get("forward_closed_count", 0),
            "forward_rv_cash_usd": fwd.get("forward_rv_cash_usd", 0.0),
            "replay_status": entry.get("replay_status"),
        })
    readiness.sort(key=lambda row: (-int(row["combined_closed_count"]), row["sleeve_key"]))

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "status": "accepted",
        "decision": "accepted_measurement_repair_post_acceptance_oos_replay_readiness",
        "hypothesis": (
            "Accepted default-off paper sleeves show near-zero closed forward rows "
            "mainly because production accumulated on a starved 27-57 name fallback "
            "universe; an out-of-sample shared-helper replay over 2026-04-22..2026-06-11 "
            "on the unified universe, segmented from genuine forward rows, restores a "
            "usable per-sleeve activation-readiness surface."
        ),
        "change_type": "identity_or_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "mechanism_family": "measurement_repair",
        "nearby_prior_experiments": [
            "exp-20260611-020",
            "exp-20260612-002",
            "exp-20260612-004",
            "exp-20260612-010",
            "exp-20260612-012",
        ],
        "oos_window": OOS_CFG,
        "oos_window_note": (
            "Strictly after the frozen Gate-4 windows (which end 2026-04-21), so this "
            "replay is out-of-sample for every accepted adapter. It is still replay, "
            "not production-forward evidence: it cannot prove the daily pipeline "
            "emits the same candidates. Activation still requires the declared "
            "envelope and a narrow activation Gate 1-4 per adapter."
        ),
        "baseline_core_metrics": framework.overlay_helper._metrics(baseline),
        "core_entry_day_count": len(core_entries),
        "sleeves": framework._safe(sleeves),
        "genuine_forward_rows_by_sleeve_dir": forward_rows,
        "readiness_report": readiness,
        "readiness_rule": {
            "min_combined_closed": READINESS_MIN_COMBINED_CLOSED,
            "rv_cash_positive_required": True,
            "rv_spy_positive_required": True,
            "note": "Bucket label only; not an activation decision.",
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "replay_only": True,
            "shared_policy_changed": False,
            "sleeve_state_files_modified": False,
            "production_impact": "read_only_audit",
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Sleeve | Bucket | Combined closed | OOS closed | OOS rv vs SPY | Forward closed |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["readiness_report"]:
        rows.append(
            "| {sleeve} | {bucket} | {combined} | {oos} | {rv} | {fwd} |".format(
                sleeve=row["sleeve_key"],
                bucket=row["readiness_bucket"],
                combined=row["combined_closed_count"],
                oos=row["oos_closed_count"],
                rv=row["oos_rv_spy_usd"],
                fwd=row["forward_closed_count"],
            )
        )
    title = "# " + EXPERIMENT_ID + " Post-Acceptance OOS Replay Readiness"
    status_line = "Status: " + str(payload["status"])
    parts = [title, "", status_line, "", payload["oos_window_note"], ""]
    parts.extend(rows)
    parts.extend(["", "No JavaScript was used."])
    newline = chr(10)
    return newline.join(parts) + newline


def persist(payload: dict[str, Any]) -> None:
    framework._write_json(OUT_JSON, payload)
    log_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "measurement_repair",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": True,
        "accepted_alpha": False,
        "mechanism_family": "measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "oos_window": payload["oos_window"],
        "readiness_report": payload["readiness_report"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": {
            "why_result_happened": (
                "Genuine forward rows are near zero because daily sleeve accumulation "
                "ran on the starved fallback universe; the OOS replay quantifies what "
                "the unified universe would have produced after acceptance, without "
                "rewriting forward history."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not backfill replay rows into sleeve state/snapshot files and do "
                "not treat OOS replay rows as production-forward evidence."
            ),
            "new_evidence_required": (
                "Activation of any activation_gate_candidate sleeve needs its declared "
                "execution envelope plus a narrow activation Gate 1-4, and genuine "
                "forward rows accumulating under the unified universe."
            ),
        },
        "anti_js": "No JavaScript was used.",
    }
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": True,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "readiness_report": payload["readiness_report"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": log_record["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "decision": payload["decision"],
        "summary": payload["oos_window_note"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card_file": _repo_rel(CARD_MD),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    persist(payload)
    print(json.dumps(framework._safe(payload["readiness_report"]), indent=2))


if __name__ == "__main__":
    main()
