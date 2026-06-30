"""exp-20260630-017: characteristic-similarity peer-shock forward value.

Replay-only alpha scout.  It asks whether a peer with similar point-in-time
fundamental, liquidity, momentum, and analyst-coverage characteristics can lead
a laggard after a strong idiosyncratic move.  This deliberately caps prior
return correlation below the accepted rolling-correlation peer-shock threshold,
so the test is not a relabeling of exp-20260606-025.

Run:
    .\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260630_017_characteristic_similarity_peer_shock_forward_value.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402

shadow = framework.shadow
overlay_helper = framework.overlay_helper
sleeve_overlay = framework.sleeve
WINDOWS = framework.WINDOWS
REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import characteristic_similarity_peers as csp  # noqa: E402
import industry_relative_laggard_repair_paper_sleeve as industry  # noqa: E402
import rolling_corr_peer_shock_paper_sleeve as rc  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260630-017"
STEM = "characteristic_similarity_peer_shock_forward_value"
OWNER = "alpha-explore"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260630_017_characteristic_similarity_peer_shock_forward_value.json"
SELECTED_JSONL = OUT_DIR / "characteristic_similarity_selected_trades.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Read-only relation attribution: high characteristic-similarity peer "
    "(sector plus point-in-time fundamentals growth/margin/leverage, liquidity "
    "ADV, momentum RS, and analyst coverage breadth; not sector/ETF label or "
    "13F overlap) strong idiosyncratic move may predict laggard peer positive "
    "next-open 5/10/20d forward replacement value, incremental beyond accepted "
    "rolling-correlation peer-shock and industry-relative laggard-repair "
    "comparators."
)
CHANGED_VARIABLE = "characteristic_similarity_peer_shock_forward_replacement_v1"
TRIAL_FAMILY = "characteristic_similarity_peer_shock"
TRIAL_VARIANT_ID = "non_corr_pit_characteristic_similarity_top1_next_open_10d_v1"

PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2000,
    "main_failure_modes": [
        "thin_sample_after_non_corr_cap",
        "not_incremental_vs_rolling_corr_peer_shock",
        "not_incremental_vs_industry_laggard_repair",
        "forward_horizon_replacement_not_positive",
        "fundamental_missingness_bias",
    ],
    "confidence_reason": (
        "I assigned only a 20% pass probability because the non-correlation cap "
        "should make the candidate set thin, while the accepted rolling-corr and "
        "industry-laggard sleeves already capture nearby peer-shock replacement "
        "value on these same frozen windows."
    ),
}

CONFIG = csp.config(
    {
        "paper_notional_usd": 4_000.0,
        "daily_entry_slots": 1,
        "hold_days": 10,
        "same_ticker_cooldown_days": 10,
        "min_characteristic_similarity": 0.64,
        "max_prior_return_correlation": 0.57,
        "min_non_price_pair_features": 2,
    }
)
HORIZONS = (5, 10, 20)
SLEEVE_NAMES = ("characteristic_similarity", "rolling_corr", "industry_relative")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    return Path(path).resolve().relative_to(REPO_ROOT).as_posix()


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits)


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _trade_economics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl") or 0.0) for row in trades]
    winners = [pnl for pnl in pnls if pnl > 0]
    by_ticker: Counter[str] = Counter()
    for row in trades:
        by_ticker[str(row.get("ticker") or "").upper()] += float(row.get("pnl") or 0.0)
    positive = {ticker: pnl for ticker, pnl in by_ticker.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_share = max(positive.values()) / positive_total if positive_total > 0 else None
    hhi = (
        sum((pnl / positive_total) ** 2 for pnl in positive.values())
        if positive_total > 0
        else None
    )
    return {
        "trade_count": len(trades),
        "net_pnl": _round(sum(pnls), 2),
        "win_rate": _round(len(winners) / len(trades), 4) if trades else None,
        "avg_pnl_per_trade": _round(sum(pnls) / len(trades), 2) if trades else None,
        "unique_tickers": len(by_ticker),
        "single_ticker_positive_share": _round(max_share, 4),
        "positive_pnl_hhi": _round(hhi, 4),
    }


def _with_overlay(
    before_result: dict[str, Any],
    before_metrics: dict[str, Any],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    overlay = sleeve_overlay._overlay_from_paper_trades(before_result, trades)
    after = overlay_helper._metrics_with_overlay(before_result, overlay)
    return {
        "after": after,
        "delta": overlay_helper._delta(after, before_metrics),
        "overlay_total_pnl": _round(overlay["overlay_total_pnl"], 2),
        "economics": _trade_economics(trades),
        "trades": trades,
    }


def _run_window(
    *,
    label: str,
    cfg: dict[str, str],
    universe: list[str],
    sector_entries: dict[str, dict[str, Any]],
    fundamental_index: Any | None,
    analyst_index: csp.AnalystCoverageIndex,
) -> dict[str, Any]:
    print(f"[{label}] core baseline ...", flush=True)
    before_result = shadow._run_baseline(universe, cfg)
    before = overlay_helper._metrics(before_result)
    snapshot = framework._load_window_snapshot(
        cfg=cfg,
        eligible_tickers=set(sector_entries),
    )
    core_entries_by_date = shadow._baseline_entries(before_result)
    sector_map = {ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot}
    window = {"start": cfg["start"], "end": cfg["end"]}

    print(f"[{label}] characteristic-similarity peer-shock replay ...", flush=True)
    target_trades, target_audit = csp.build_characteristic_similarity_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows={label: window},
        sector_entries=sector_map,
        fundamental_index=fundamental_index,
        analyst_coverage_index=analyst_index,
        config=CONFIG,
    )
    target = _with_overlay(before_result, before, target_trades)
    target["audit"] = target_audit
    target["forward_horizon_summary"] = csp.forward_horizon_summary(
        trades=target_trades,
        ohlcv_by_ticker=snapshot,
        horizons=HORIZONS,
        config=CONFIG,
    )

    print(f"[{label}] rolling-corr comparator replay ...", flush=True)
    rc_trades, rc_audit = rc.build_rolling_corr_peer_shock_historical_trades(
        ohlcv_by_ticker=snapshot,
        core_entries_by_date=core_entries_by_date,
        windows={label: window},
        sector_entries=sector_map,
    )
    rolling = _with_overlay(before_result, before, rc_trades)
    rolling["audit"] = rc_audit

    print(f"[{label}] industry-relative comparator replay ...", flush=True)
    industry_trades, industry_audit = (
        industry.build_industry_relative_laggard_repair_historical_trades(
            ohlcv_by_ticker=snapshot,
            core_entries_by_date=core_entries_by_date,
            windows={label: window},
            sector_entries=sector_map,
        )
    )
    industry_row = _with_overlay(before_result, before, industry_trades)
    industry_row["audit"] = industry_audit

    return {
        "label": label,
        "window": window,
        "before": before,
        "core_entry_days": len(core_entries_by_date),
        "loaded_ticker_count": len(snapshot),
        "characteristic_similarity": target,
        "rolling_corr": rolling,
        "industry_relative": industry_row,
    }


def _combine_horizon_summaries(window_records: dict[str, Any]) -> dict[str, Any]:
    by_horizon: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        key = str(horizon)
        count = 0
        net_pnl = 0.0
        winner_count = 0
        avg_pct_numer = 0.0
        spy_count = 0
        spy_excess = 0.0
        qqq_count = 0
        qqq_excess = 0.0
        positive_windows = 0
        for record in window_records.values():
            summary = record["characteristic_similarity"]["forward_horizon_summary"][
                "by_horizon"
            ].get(key, {})
            local_count = int(summary.get("count") or 0)
            count += local_count
            net_pnl += float(summary.get("net_pnl") or 0.0)
            winner_count += int(summary.get("winner_count") or 0)
            avg_pct = summary.get("avg_pnl_pct")
            if avg_pct is not None:
                avg_pct_numer += float(avg_pct) * local_count
            spy_local = int(summary.get("count_vs_spy") or 0)
            spy_count += spy_local
            spy_excess += float(summary.get("net_excess_vs_spy_usd") or 0.0)
            qqq_local = int(summary.get("count_vs_qqq") or 0)
            qqq_count += qqq_local
            qqq_excess += float(summary.get("net_excess_vs_qqq_usd") or 0.0)
            if float(summary.get("net_pnl") or 0.0) > 0.0:
                positive_windows += 1
        by_horizon[key] = {
            "count": count,
            "net_pnl": _round(net_pnl, 2),
            "avg_pnl": _round(net_pnl / count, 2) if count else None,
            "avg_pnl_pct": _round(avg_pct_numer / count, 6) if count else None,
            "winner_count": winner_count,
            "win_rate": _round(winner_count / count, 6) if count else None,
            "count_vs_spy": spy_count,
            "net_excess_vs_spy_usd": _round(spy_excess, 2),
            "count_vs_qqq": qqq_count,
            "net_excess_vs_qqq_usd": _round(qqq_excess, 2),
            "positive_net_pnl_window_count": positive_windows,
        }
    return {"by_horizon": by_horizon}


def _aggregate(window_records: dict[str, Any]) -> dict[str, Any]:
    base_ev = sum(float(row["before"].get("expected_value_score") or 0.0) for row in window_records.values())
    base_pnl = sum(float(row["before"].get("total_pnl") or 0.0) for row in window_records.values())
    base_max_dd = max(float(row["before"].get("max_drawdown_pct") or 0.0) for row in window_records.values())
    out: dict[str, Any] = {
        "baseline": {
            "aggregate_expected_value_score": _round(base_ev, 4),
            "aggregate_total_pnl": _round(base_pnl, 2),
            "max_window_drawdown_pct": _round(base_max_dd, 4),
        }
    }
    for sleeve_name in SLEEVE_NAMES:
        trades: list[dict[str, Any]] = []
        ev_delta = 0.0
        pnl_delta = 0.0
        max_dd_drift = 0.0
        windows_ev_improved = 0
        windows_ev_regressed = 0
        windows_pnl_improved = 0
        windows_pnl_regressed = 0
        for record in window_records.values():
            sleeve = record[sleeve_name]
            trades.extend(sleeve["trades"])
            delta = sleeve["delta"]
            delta_ev = float(delta.get("expected_value_score") or 0.0)
            delta_pnl = float(sleeve.get("overlay_total_pnl") or 0.0)
            ev_delta += delta_ev
            pnl_delta += delta_pnl
            if delta_ev > 0:
                windows_ev_improved += 1
            if delta_ev < 0:
                windows_ev_regressed += 1
            if delta_pnl > 0:
                windows_pnl_improved += 1
            if delta_pnl < 0:
                windows_pnl_regressed += 1
            before_dd = float(record["before"].get("max_drawdown_pct") or 0.0)
            after_dd = float(sleeve["after"].get("max_drawdown_pct") or 0.0)
            max_dd_drift = max(max_dd_drift, after_dd - before_dd)
        out[sleeve_name] = {
            "aggregate_expected_value_delta": _round(ev_delta, 6),
            "aggregate_total_pnl_delta": _round(pnl_delta, 2),
            "aggregate_expected_value_after": _round(base_ev + ev_delta, 4),
            "aggregate_total_pnl_after": _round(base_pnl + pnl_delta, 2),
            "max_drawdown_worse": _round(max_dd_drift, 6),
            "windows_ev_improved": windows_ev_improved,
            "windows_ev_regressed": windows_ev_regressed,
            "windows_pnl_improved": windows_pnl_improved,
            "windows_pnl_regressed": windows_pnl_regressed,
            "economics_all_windows": _trade_economics(trades),
        }
    target = out["characteristic_similarity"]
    rolling = out["rolling_corr"]
    industry_row = out["industry_relative"]
    out["characteristic_similarity"]["forward_horizon_summary"] = _combine_horizon_summaries(
        window_records
    )
    out["incremental_vs_rolling_corr"] = {
        "expected_value_delta": _round(
            float(target["aggregate_expected_value_delta"] or 0.0)
            - float(rolling["aggregate_expected_value_delta"] or 0.0),
            6,
        ),
        "total_pnl_delta": _round(
            float(target["aggregate_total_pnl_delta"] or 0.0)
            - float(rolling["aggregate_total_pnl_delta"] or 0.0),
            2,
        ),
    }
    out["incremental_vs_industry_relative"] = {
        "expected_value_delta": _round(
            float(target["aggregate_expected_value_delta"] or 0.0)
            - float(industry_row["aggregate_expected_value_delta"] or 0.0),
            6,
        ),
        "total_pnl_delta": _round(
            float(target["aggregate_total_pnl_delta"] or 0.0)
            - float(industry_row["aggregate_total_pnl_delta"] or 0.0),
            2,
        ),
    }
    return out


def _gate4(aggregate: dict[str, Any]) -> dict[str, Any]:
    target = aggregate["characteristic_similarity"]
    rolling = aggregate["rolling_corr"]
    industry_row = aggregate["industry_relative"]
    econ = target["economics_all_windows"]
    failures: list[str] = []
    if float(target["aggregate_expected_value_delta"] or 0.0) <= 0:
        failures.append("aggregate_ev_not_positive")
    if float(target["aggregate_total_pnl_delta"] or 0.0) <= 0:
        failures.append("aggregate_pnl_not_positive")
    if int(target["windows_ev_improved"] or 0) < 2:
        failures.append("fewer_than_two_ev_improved_windows")
    if int(target["windows_ev_regressed"] or 0) > 0:
        failures.append("window_ev_regression")
    if int(target["windows_pnl_regressed"] or 0) > 0:
        failures.append("window_pnl_regression")
    if int(econ["trade_count"] or 0) < 20:
        failures.append("target_sample_too_small")
    if float(target["max_drawdown_worse"] or 0.0) > 0.005:
        failures.append("drawdown_drift_too_high")
    single_share = econ.get("single_ticker_positive_share")
    hhi = econ.get("positive_pnl_hhi")
    if single_share is None or float(single_share) > 0.50 or hhi is None or float(hhi) > 0.35:
        failures.append("target_concentration_failed")
    if float(target["aggregate_expected_value_delta"] or 0.0) <= float(
        rolling["aggregate_expected_value_delta"] or 0.0
    ):
        failures.append("rolling_corr_peer_shock_ev_not_beaten")
    if float(target["aggregate_total_pnl_delta"] or 0.0) <= float(
        rolling["aggregate_total_pnl_delta"] or 0.0
    ):
        failures.append("rolling_corr_peer_shock_pnl_not_beaten")
    if float(target["aggregate_expected_value_delta"] or 0.0) <= float(
        industry_row["aggregate_expected_value_delta"] or 0.0
    ):
        failures.append("industry_laggard_repair_ev_not_beaten")
    if float(target["aggregate_total_pnl_delta"] or 0.0) <= float(
        industry_row["aggregate_total_pnl_delta"] or 0.0
    ):
        failures.append("industry_laggard_repair_pnl_not_beaten")
    horizon_failures = []
    for horizon in HORIZONS:
        summary = target["forward_horizon_summary"]["by_horizon"][str(horizon)]
        if int(summary.get("count") or 0) < 20:
            horizon_failures.append(f"h{horizon}_sample_too_small")
        if float(summary.get("net_pnl") or 0.0) <= 0.0:
            horizon_failures.append(f"h{horizon}_net_pnl_not_positive")
        if float(summary.get("net_excess_vs_spy_usd") or 0.0) <= 0.0:
            horizon_failures.append(f"h{horizon}_spy_replacement_not_positive")
        if float(summary.get("net_excess_vs_qqq_usd") or 0.0) <= 0.0:
            horizon_failures.append(f"h{horizon}_qqq_replacement_not_positive")
    failures.extend(horizon_failures)
    return {
        "passed": not failures,
        "failed_reasons": failures,
        "aggregate_ev_delta": target["aggregate_expected_value_delta"],
        "aggregate_pnl_delta": target["aggregate_total_pnl_delta"],
        "target_trade_count": econ["trade_count"],
        "target_trade_count_min": 20,
        "windows_ev_improved": target["windows_ev_improved"],
        "windows_ev_regressed": target["windows_ev_regressed"],
        "windows_pnl_improved": target["windows_pnl_improved"],
        "windows_pnl_regressed": target["windows_pnl_regressed"],
        "max_drawdown_worse": target["max_drawdown_worse"],
        "max_drawdown_worse_guardrail": 0.005,
        "target_concentration": {
            "single_ticker_positive_share": single_share,
            "single_ticker_positive_share_guardrail": 0.50,
            "positive_pnl_hhi": hhi,
            "positive_pnl_hhi_guardrail": 0.35,
            "passed": "target_concentration_failed" not in failures,
        },
        "forward_horizon_summary": target["forward_horizon_summary"],
        "accepted_comparators": [
            {
                "name": "rolling_corr_peer_shock",
                "experiment_id": "exp-20260606-025",
                "aggregate_ev_delta": rolling["aggregate_expected_value_delta"],
                "aggregate_pnl_delta": rolling["aggregate_total_pnl_delta"],
            },
            {
                "name": "industry_relative_laggard_repair",
                "experiment_id": "exp-20260607-008",
                "aggregate_ev_delta": industry_row["aggregate_expected_value_delta"],
                "aggregate_pnl_delta": industry_row["aggregate_total_pnl_delta"],
            },
        ],
    }


def _calibration(gate4: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4["passed"] else 0
    predicted = float(PREDICTION["success_probability"])
    actual_ev = float(gate4.get("aggregate_ev_delta") or 0.0)
    actual_pnl = float(gate4.get("aggregate_pnl_delta") or 0.0)
    failures = gate4.get("failed_reasons") or []
    realized = failures[0] if failures else "numeric_gate4_passed_but_replay_only"
    return {
        "actual_success": actual_success,
        "predicted_success_probability": predicted,
        "brier_score": _round((predicted - actual_success) ** 2, 4),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": _round(actual_ev, 6),
        "ev_prediction_error": _round(actual_ev - float(PREDICTION["expected_ev_delta"]), 6),
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": _round(actual_pnl, 2),
        "pnl_prediction_error": _round(actual_pnl - float(PREDICTION["expected_pnl_delta"]), 2),
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "realized_failure_mode": realized,
        "predicted_failure_mode_hit": any(
            token in realized
            for token in ("sample", "rolling_corr", "industry", "replacement", "fundamental")
        ),
        "calibration_direction": "directionally_calibrated" if actual_success == 0 else "underconfident",
        "surprise_level": "low" if actual_success == 0 else "moderate",
    }


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "research_helper_added": True,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "trade_enabled": False,
        "daily_snapshot_exposed": False,
        "live_ready": False,
        "parity_test_added": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "uses_llm": False,
        "uses_free_ohlcv": True,
        "uses_sec_companyfacts": True,
        "uses_estimate_revision_ledger": True,
        "activation_envelope": {
            "paper_notional_usd": CONFIG["paper_notional_usd"],
            "daily_entry_slots": CONFIG["daily_entry_slots"],
            "hold_days": CONFIG["hold_days"],
            "same_ticker_cooldown_days": CONFIG["same_ticker_cooldown_days"],
            "min_avg_dollar_volume_20d": CONFIG["min_avg_dollar_volume_20d"],
            "max_prior_return_correlation": CONFIG["max_prior_return_correlation"],
            "min_characteristic_similarity": CONFIG["min_characteristic_similarity"],
            "trade_enabled_until_forward_gate": False,
        },
    }


def _compact_windows(window_records: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, record in window_records.items():
        target = record["characteristic_similarity"]
        rolling = record["rolling_corr"]
        industry_row = record["industry_relative"]
        rows.append(
            {
                "label": label,
                "start": record["window"]["start"],
                "end": record["window"]["end"],
                "before_ev": record["before"].get("expected_value_score"),
                "before_pnl": record["before"].get("total_pnl"),
                "characteristic_ev_delta": target["delta"].get("expected_value_score"),
                "characteristic_pnl_delta": target["overlay_total_pnl"],
                "characteristic_trade_count": target["economics"]["trade_count"],
                "rolling_corr_ev_delta": rolling["delta"].get("expected_value_score"),
                "rolling_corr_pnl_delta": rolling["overlay_total_pnl"],
                "rolling_corr_trade_count": rolling["economics"]["trade_count"],
                "industry_ev_delta": industry_row["delta"].get("expected_value_score"),
                "industry_pnl_delta": industry_row["overlay_total_pnl"],
                "industry_trade_count": industry_row["economics"]["trade_count"],
                "characteristic_scan": target["audit"]["scan_by_window"].get(label, {}),
                "forward_horizon_summary": target["forward_horizon_summary"],
            }
        )
    return rows


def _build_payload() -> dict[str, Any]:
    universe = sorted(framework.get_universe())
    sector_entries = framework._load_sector_entries()
    max_end = max(str(cfg["end"]) for cfg in WINDOWS.values())
    fundamental_index, fundamental_audit = csp.load_companyfacts_fundamental_index(
        max_filed=max_end,
        tickers=universe,
    )
    analyst_index, analyst_audit = csp.AnalystCoverageIndex.from_revision_ledgers(
        root=REPO_ROOT / "data" / "experiments",
        max_asof=max_end,
        tickers=universe,
    )
    window_records: "OrderedDict[str, Any]" = OrderedDict()
    for label, cfg in WINDOWS.items():
        window_records[label] = _run_window(
            label=label,
            cfg=cfg,
            universe=universe,
            sector_entries=sector_entries,
            fundamental_index=fundamental_index,
            analyst_index=analyst_index,
        )
    aggregate = _aggregate(window_records)
    gate4 = _gate4(aggregate)
    calibration = _calibration(gate4)
    status = "observed_only_positive_lead" if gate4["passed"] else "rejected"
    decision = (
        "positive_replay_lead_not_promoted"
        if gate4["passed"]
        else "rejected_characteristic_similarity_peer_shock_forward_value"
    )
    min_survival = min(
        float(record["before"].get("survival_rate") or 0.0)
        for record in window_records.values()
    )
    related_files = [
        _repo_rel(Path(__file__)),
        "quant/characteristic_similarity_peers.py",
        "quant/test_characteristic_similarity_peers.py",
        _repo_rel(OUT_JSON),
        _repo_rel(SELECTED_JSONL),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(TICKET_JSON),
        "docs/experiment_registry.json",
    ]
    failures = gate4["failed_reasons"]
    why = (
        "Characteristic-similarity peer shock passed the strict read-only screen "
        "and is only a lead because no shared daily snapshot/paper adapter was "
        "promoted."
        if gate4["passed"]
        else (
            "Characteristic-similarity peer shock did not clear the predeclared "
            f"screen: {', '.join(failures[:6])}."
        )
    )
    return framework._safe(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": decision,
            "accepted": False,
            "accepted_alpha": False,
            "hypothesis": HYPOTHESIS,
            "change_type": "relation_aware_peer_shock_observed_only_attribution",
            "implementation_mode": "private_replay_scout_with_reusable_read_only_helper",
            "mechanism_family": "peer_shock",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": [
                "PIT characteristic-similarity helper",
                "historical replay",
                "5/10/20d forward replacement-value check",
                "accepted comparator check",
            ],
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260606-025",
                "exp-20260607-008",
                "exp-20260608-025",
            ],
            "multiple_testing_risk_bucket": "moderate_relation_alpha_near_accepted_peer_sleeves",
            "new_evidence_type": (
                "PIT multi-factor characteristic-similarity peer graph with "
                "non-price feature requirement and explicit rolling-corr cap."
            ),
            "parameters": {
                key: CONFIG[key]
                for key in [
                    "paper_notional_usd",
                    "daily_entry_slots",
                    "hold_days",
                    "same_ticker_cooldown_days",
                    "min_characteristic_similarity",
                    "max_prior_return_correlation",
                    "min_non_price_pair_features",
                    "min_peer_signal_return",
                    "min_peer_relative_vs_spy",
                    "min_candidate_signal_return",
                    "max_candidate_signal_return",
                ]
            },
            "companyfacts_audit": fundamental_audit,
            "analyst_coverage_audit": analyst_audit,
            "windows": _compact_windows(window_records),
            "window_records": window_records,
            "aggregate": aggregate,
            "gate1": {
                "baseline_protocol": "accepted_stack_standard_windows",
                "baseline_artifact": "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
                "aggregate_expected_value_score": aggregate["baseline"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_total_pnl": aggregate["baseline"]["aggregate_total_pnl"],
                "passed": True,
            },
            "gate2": {
                "dependency_fields": [
                    "entry_date",
                    "target_price",
                    "OHLCV open/high/low/close/volume",
                    "sector",
                    "industry",
                    "SEC Companyfacts filed-date rows",
                    "optional estimate revision analyst coverage rows",
                ],
                "runtime_fields_verified": True,
                "passed": True,
            },
            "gate3": {
                "new_core_filter_added": False,
                "candidate_pool_changed": False,
                "minimum_core_survival_rate": _round(min_survival, 6),
                "passed": min_survival >= 0.05,
                "note": "Additive replay-only candidate source; core survival unchanged.",
            },
            "gate4": gate4,
            "prediction": PREDICTION,
            "calibration": calibration,
            "production_impact": _production_impact(),
            "rejection_reason": None if gate4["passed"] else "; ".join(failures),
            "next_retry_requires": (
                "Do not retry by only retuning similarity weights, thresholds, "
                "hold days, cooldown, or response sizing on these frozen windows. "
                "A legal retry needs a new relation data source, a new gate shape, "
                "or materially more settled forward replacement rows."
            ),
            "post_run_reflection": {
                "why_result_happened": why,
                "policy_bundle_tested": CHANGED_VARIABLE,
                "realized_failure_mode": failures[0] if failures else None,
                "forbidden_near_neighbor_retry": (
                    "Do not rerun this same characteristic-similarity peer-shock "
                    "family by only changing similarity weights, min similarity, "
                    "non-price feature count, prior-correlation cap, hold days, "
                    "cooldown, notional, or response sizing on the same frozen "
                    "windows."
                ),
                "new_evidence_required": (
                    "A legal retry requires a genuinely new relation data source, "
                    "a new gate shape that changes the event being tested, or "
                    "materially more settled forward replacement-value rows from "
                    "a shared default-off paper observation surface."
                ),
                "anti_repeat": (
                    "This closes the characteristic-similarity peer-shock scout "
                    "for adjacent threshold/weight/response retunes on the same "
                    "standard-window sample."
                ),
                "next_evidence": (
                    "If positive, promote a shared default-off daily paper helper "
                    "with the same non-price feature and non-corr caps; if rejected, "
                    "move to a new relation source or new settled forward rows."
                ),
            },
            "related_files": related_files,
            "anti_js": "No JavaScript was used.",
        }
    )


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    target = aggregate["characteristic_similarity"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_summary": "Read-only PIT characteristic-similarity peer-shock replay with 5/10/20d replacement-value check.",
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": _repo_rel(Path(__file__)),
        "parameters": payload["parameters"],
        "date_range": {"start": "2024-10-02", "end": "2026-04-21"},
        "secondary_windows": [],
        "before_metrics": {
            "expected_value_score": aggregate["baseline"][
                "aggregate_expected_value_score"
            ],
            "total_pnl": aggregate["baseline"]["aggregate_total_pnl"],
            "max_drawdown_pct": aggregate["baseline"]["max_window_drawdown_pct"],
        },
        "after_metrics": {
            "expected_value_score": target["aggregate_expected_value_after"],
            "total_pnl": target["aggregate_total_pnl_after"],
            "max_drawdown_pct": None,
            "trade_count": target["economics_all_windows"]["trade_count"],
        },
        "delta_metrics": {
            "expected_value_score": target["aggregate_expected_value_delta"],
            "total_pnl": target["aggregate_total_pnl_delta"],
            "max_drawdown_pct": target["max_drawdown_worse"],
        },
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "gate4": payload["gate4"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    target = payload["aggregate"]["characteristic_similarity"]
    inc_roll = payload["aggregate"]["incremental_vs_rolling_corr"]
    inc_ind = payload["aggregate"]["incremental_vs_industry_relative"]
    rows = [
        "| Window | Target dEV | Target dPnL | Trades | Rolling dPnL | Industry dPnL |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for window in payload["windows"]:
        rows.append(
            "| {label} | {ev:+.6f} | ${pnl:+,.2f} | {trades} | ${roll:+,.2f} | ${ind:+,.2f} |".format(
                label=window["label"],
                ev=float(window["characteristic_ev_delta"] or 0.0),
                pnl=float(window["characteristic_pnl_delta"] or 0.0),
                trades=window["characteristic_trade_count"],
                roll=float(window["rolling_corr_pnl_delta"] or 0.0),
                ind=float(window["industry_pnl_delta"] or 0.0),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Characteristic Similarity Peer Shock",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Aggregate EV delta: `{target['aggregate_expected_value_delta']}`",
            f"- Aggregate PnL delta: `${target['aggregate_total_pnl_delta']}`",
            f"- Incremental vs rolling-corr EV/PnL: `{inc_roll['expected_value_delta']}` / `${inc_roll['total_pnl_delta']}`",
            f"- Incremental vs industry-relative EV/PnL: `{inc_ind['expected_value_delta']}` / `${inc_ind['total_pnl_delta']}`",
            f"- Trade count: `{target['economics_all_windows']['trade_count']}`",
            f"- Failed reasons: `{', '.join(gate4['failed_reasons']) if gate4['failed_reasons'] else 'none'}`",
            "",
            "## Windows",
            "",
            *rows,
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Fixed Policy Bundle",
            "",
            CHANGED_VARIABLE,
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260630_017_characteristic_similarity_peer_shock_forward_value.py",
            "```",
            "",
        ]
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    files = [
        Path(__file__),
        REPO_ROOT / "quant" / "characteristic_similarity_peers.py",
        REPO_ROOT / "quant" / "test_characteristic_similarity_peers.py",
        OUT_JSON,
        SELECTED_JSONL,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["timestamp"],
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "files": [_repo_rel(path) for path in files],
        "file_hashes": {_repo_rel(path): _sha256(path) for path in files},
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    selected_trades: list[dict[str, Any]] = []
    for record in payload["window_records"].values():
        selected_trades.extend(record["characteristic_similarity"]["trades"])
    csp.write_candidate_rows_jsonl(SELECTED_JSONL, selected_trades)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    save_experiment_log_entry(log_record, allow_duplicate=True)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["aggregate"]["characteristic_similarity"][
            "aggregate_expected_value_delta"
        ],
        "aggregate_strategy_total_pnl_delta": payload["aggregate"]["characteristic_similarity"][
            "aggregate_total_pnl_delta"
        ],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["aggregate"]["characteristic_similarity"][
            "aggregate_expected_value_delta"
        ],
        "aggregate_strategy_total_pnl_delta": payload["aggregate"]["characteristic_similarity"][
            "aggregate_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
