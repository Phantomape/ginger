"""Exact current-paper-surface plus core allocator for exp-20260817-001.

This module is evaluation-only.  It inventories the 41 surfaces registered by
the latest paper-sleeve execution contract, reconstructs only complete
current-rule classic-window paths, and searches capital-neutral sparse
allocations.  It never changes production signals, orders, ranking, sizing,
or exits.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from quant import historical_current_contract_reassessment as reassess
from quant import portfolio_contribution_batch as pc


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "exp-20260817-001"
WINDOWS = ("old_thin", "mid_weak", "late_strong")
PORTFOLIO_CAPITAL_USD = 100_000.0
RECONSTRUCTION_CAPITAL_USD = 10_000.0
TOTAL_PAPER_CAP = 0.10
SURFACE_CAP = 0.05
MAX_ACTIVE_SURFACES = 4
COARSE_LEVELS = (0.025, 0.05)
REFINED_STEP = 0.005
MIN_RECENT_SETTLED_ROWS = 5

SNAPSHOT_PATH = Path("data/daily/signals/quant/quant_signals_20260815.json")
SNAPSHOT_SHA256 = "d56f921be7edb7ff42399644c211967c134948fefc0a56fe052314e5d1d80c15"
FORWARD_PATH = Path("data/paper_sleeves/forward_replacement_value.jsonl")
FORWARD_SHA256 = "f577a0784bdb64664d1fb6e3504f8b9acc6cbe8053329d593214465f450d7f78"
OHLCV_PATH = Path("data/experiments/exp-20260716-011/candidate_ohlcv_rowset.json.gz")
OHLCV_SHA256 = "b432672340b7dc2fdc05a08d561d6229c0c85827b05618cc9eeff3efb8ef4048"


def _spec(
    surface: str,
    sleeve: str,
    rule_version: str,
    *,
    paper_enabled: bool = True,
    artifact: str | None = None,
    trade_key: str | None = None,
    ineligible_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "surface": surface,
        "sleeve": sleeve,
        "rule_version": rule_version,
        "paper_enabled": paper_enabled,
        "artifact": artifact,
        "trade_key": trade_key,
        "preflight_ineligible_reason": ineligible_reason,
    }


SURFACE_SPECS = (
    _spec("form4_event_sleeve", "FORM4_EVENT_SLEEVE_PAPER", "form4_event_v1", artifact="data/experiments/exp-20260504-009/form4_event_sleeve_replay.json", ineligible_reason="historical replay predates the complete current queue/sizing rule"),
    _spec("sec_negative_event_sleeve", "SEC_NEGATIVE_REACTION_EVENT_SLEEVE_PAPER", "sec_negative_reaction_event_v1", ineligible_reason="no complete current-rule classic trade path"),
    _spec("sec_governance_event_sleeve", "SEC_GOVERNANCE_EVENT_SLEEVE_PAPER", "sec_governance_procedural_mild_reaction_v1", ineligible_reason="no complete current-rule classic trade path"),
    _spec("sec_leadership_event_sleeve", "SEC_LEADERSHIP_CHANGE_EVENT_SLEEVE_PAPER", "sec_leadership_change_negative_reaction_v1", ineligible_reason="no complete current-rule classic trade path"),
    _spec("sec_financial_report_event_sleeve", "SEC_FINANCIAL_REPORT_T1_DRIFT_EVENT_SLEEVE_PAPER", "sec_financial_report_t1_drift_v1", ineligible_reason="no complete current-rule classic trade path"),
    _spec("event_sleeve_bundle", "DEFAULT_OFF_EVENT_OVERLAY_BUNDLE_PAPER", "event_sleeve_bundle_current_v1", ineligible_reason="composite has no complete current-rule classic path and overlaps event children"),
    _spec("state_surface_sleeve", "STATE_SURFACE_SATELLITE_PAPER", "state_surface_full_v1", artifact="data/experiments/exp-20260507-016/state_surface_satellite_replay.json", ineligible_reason="artifact has metrics but no complete current-rule trade path"),
    _spec("low_deployment_etf_overlay", "LOW_DEPLOYMENT_DYNAMIC_ETF_OVERLAY_PAPER", "low_deployment_etf_cash_substitute_v1", artifact="data/experiments/exp-20260606-001/exp_20260606_001_low_deployment_etf_cash_substitute_shared_adapter.json", trade_key="trades_by_window"),
    _spec("core_misfit_paper_sleeve", "CORE_MISFIT_PAPER", "core_misfit_negative_signal_v2", artifact="data/experiments/exp-20260518-022/core_misfit_trend_only_paper_scope.json", ineligible_reason="artifact has scope metrics but no complete current-rule trade path"),
    _spec("broad_market_paper_sleeve", "BROAD_MARKET_LEADERSHIP_PAPER", "broad_market_price_floor_rank_low_extension_high_volatility_trend_persistence_v1", artifact="data/experiments/exp-20260520-004/broad_market_trend_persistence_notional.json", ineligible_reason="artifact retains only sampled adjusted trades, not the complete current-rule path"),
    _spec("macro_relief_leadership_paper_sleeve", "MACRO_RELIEF_LEADERSHIP_PAPER", "shared_macro_relief_top2_leadership_paper_adapter_v1", artifact="data/experiments/exp-20260606-020/exp_20260606_020_macro_relief_top2_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("volatility_relief_stock_leadership_paper_sleeve", "VOLATILITY_RELIEF_LEADERSHIP_PAPER", "volatility_relief_stock_leadership_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260607-019/exp_20260607_019_volatility_relief_stock_leadership_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("move_rate_volatility_relief_paper_sleeve", "MOVE_RATE_VOLATILITY_RELIEF_LEADERSHIP_PAPER", "move_rate_volatility_relief_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260711-004/exp_20260711_004_move_rate_volatility_relief_shared_paper.json", trade_key="target_trades_by_window"),
    _spec("rolling_corr_peer_shock_paper_sleeve", "ROLLING_CORR_PEER_SHOCK_CORE_FLOW_PAPER", "rolling_corr_peer_shock_core_flow_shared_adapter_v1", artifact="data/experiments/exp-20260606-025/exp_20260606_025_rolling_corr_peer_shock_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("industry_relative_laggard_repair_paper_sleeve", "INDUSTRY_RELATIVE_LAGGARD_REPAIR_PAPER", "industry_relative_laggard_repair_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260607-008/exp_20260607_008_industry_relative_laggard_repair_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("industry_stable_core_flow_paper_sleeve", "INDUSTRY_STABLE_CORE_FLOW_PAPER", "industry_stable_core_flow_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260608-008/exp_20260608_008_industry_stable_core_flow_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("turn_of_month_liquid_leadership_paper_sleeve", "TURN_OF_MONTH_LIQUID_LEADERSHIP_PAPER", "turn_of_month_liquid_leadership_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260609-027/exp_20260609_027_turn_of_month_liquid_leadership_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("deep_drawdown_rebound_paper_sleeve", "DEEP_DRAWDOWN_REBOUND_PAPER", "deep_drawdown_episode_etf_rebound_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260706-003/exp_20260706_003_deep_drawdown_rebound.json", trade_key="all_trades_by_entry_window"),
    _spec("fiftytwo_week_high_proximity_paper_sleeve", "FIFTYTWO_WEEK_HIGH_PROXIMITY_CORE_FLOW_PAPER", "fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260610-008/exp_20260610_008_fiftytwo_week_high_proximity_full_stack.json", trade_key="target_trades_by_window"),
    _spec("narrow_range_compression_breakout_paper_sleeve", "NARROW_RANGE_COMPRESSION_BREAKOUT_PAPER", "narrow_range_compression_breakout_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260608-013/exp_20260608_013_narrow_range_compression_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("distribution_day_absorption_leadership_paper_sleeve", "DISTRIBUTION_DAY_ABSORPTION_LEADERSHIP_PAPER", "distribution_day_absorption_leadership_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260611-007/exp_20260611_007_distribution_day_absorption_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("sbc_burden_improvement_paper_sleeve", "SBC_BURDEN_IMPROVEMENT_PAPER", "sbc_burden_improvement_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260616-015/exp_20260616_015_sbc_burden_improvement_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("supplier_financing_debt_relief_paper_sleeve", "SUPPLIER_FINANCING_DEBT_RELIEF_RISK_SCALED_PAPER", "supplier_financing_debt_relief_shared_risk_scaled_default_off_adapter_v1", artifact="data/experiments/exp-20260620-009/exp_20260620_009_supplier_financing_debt_relief_shared_4k_risk_scaled_adapter.json", trade_key="target_trades_by_window"),
    _spec("revision_surprise_low_extension_paper_sleeve", "REVISION_SURPRISE_LOW_EXTENSION_PAPER", "revision_surprise_low_extension_shared_default_off_adapter_v1", artifact="data/experiments/exp-20260609-011/revision_surprise_low_extension_shared_adapter.json", trade_key="target_trades_by_window"),
    _spec("accepted_helper_source_priority_allocator_paper_sleeve", "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER", "accepted_helper_source_priority_shared_default_off_allocator_v3", artifact="data/experiments/exp-20260621-007/exp_20260621_007_accepted_allocator_lagged_consensus_notional.json", ineligible_reason="current allocator artifact stores only affected rows and summaries, not its complete trade path"),
    _spec("ai_optical_paper_sleeve", "AI_OPTICAL_IWM_CONFIRMED_PAPER", "ai_optical_iwm_confirmed_fixed_notional_v1", artifact="data/experiments/exp-20260525-003/ai_optical_iwm_confirmed_fixed_notional_sleeve.json", trade_key="target_trades_by_window"),
    _spec("volatility_contraction_paper_sleeve", "VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER", "volatility_contraction_qqq_confirmed_top2_v1", artifact="data/experiments/exp-20260526-007/vcp_rank_notional_profile.json", ineligible_reason="current rank-notional profile is not materialized as a complete trade path"),
    _spec("volume_breadth_breakout_paper_sleeve", "VOLUME_BREADTH_BREAKOUT_PAPER", "volume_breadth_breakout_shared_top1_v1", artifact="data/experiments/exp-20260529-004/exp_20260529_004_vbb_cost_liquidity_support.json", trade_key="target_trades_by_window"),
    _spec("post_earnings_underpriced_drift_paper_sleeve", "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER", "post_earnings_underpriced_drift_shared_adapter_v1", artifact="data/experiments/exp-20260603-022/exp_20260603_022_post_earnings_non_core_overlap_shared_support.json", trade_key="target_trades_by_window"),
    _spec("pead_broad_universe_paper_sleeve", "PEAD_BROAD_UNIVERSE_PAPER", "pead_broad_universe_paper_sleeve_v1", artifact="data/experiments/exp-20260607-025/exp_20260607_025_pead_broad_universe_historical_replay.json", trade_key="target_trades_by_window"),
    _spec("alpha_score_market_regime_paper_sleeve", "ALPHA_SCORE_MARKET_REGIME_PAPER", "alpha_score_market_regime_safe_notional_shared_v1", artifact="data/experiments/exp-20260531-025/exp_20260531_025_alpha_score_source_consensus_adapter.json", trade_key="target_trades_by_window"),
    _spec("accepted_source_consensus_paper_sleeve", "ACCEPTED_SOURCE_CONSENSUS_PAPER", "accepted_source_consensus_shared_v1", artifact="data/experiments/exp-20260531-029/exp_20260531_029_accepted_source_consensus_adapter.json", trade_key="target_trades_by_window"),
    _spec("free_data_cross_source_consensus_paper_sleeve", "ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER", "accepted_free_data_cross_source_consensus_shared_v1", artifact="data/experiments/exp-20260604-008/lagged_independent_source_consensus.json", trade_key="target_trades_by_window"),
    _spec("fundamental_growth_rs_paper_sleeve", "FUNDAMENTAL_GROWTH_RS_PAPER", "fundamental_growth_rs_gross_margin_shared_adapter_v1", artifact="data/experiments/exp-20260602-010/exp_20260602_010_companyfacts_sector_residual_adapter.json", ineligible_reason="current artifact stores summaries/samples but no complete target trade path"),
    _spec("finra_iwm_paper_sleeve", "FINRA_IWM_CONFIRMED_PAPER", "finra_iwm_borrow_pressure_shared_v1", paper_enabled=False, artifact="data/experiments/exp-20260603-006/exp_20260603_006_finra_borrow_pressure_candidate_pool.json", trade_key="target_trades_by_window", ineligible_reason="paper_snapshot_disabled"),
    _spec("sec_ftd_finra_paper_sleeve", "SEC_FTD_FINRA_CONFIRMED_PAPER", "sec_ftd_finra_shared_default_off_adapter_v1", paper_enabled=False, artifact="data/experiments/exp-20260604-026/exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool.json", trade_key="target_trades_by_window", ineligible_reason="paper_snapshot_disabled"),
    _spec("sec_item101_contract_relation_paper_sleeve", "SEC_ITEM101_CONTRACT_RELATION_ISSUER_SELF_PAPER", "sec_item101_contract_relation_issuer_self_top1_v1", paper_enabled=False, artifact="data/experiments/exp-20260703-019/exp_20260703_019_sec_item101_contract_relation_shared_paper.json", trade_key="target_trades_by_window", ineligible_reason="paper_snapshot_disabled"),
    _spec("moomoo_capital_flow_paper_sleeve", "MOOMOO_CAPITAL_FLOW_ACCUMULATION_PAPER", "moomoo_capital_flow_day_main_inflow_top1_v1", paper_enabled=False, artifact="data/experiments/exp-20260702-019/exp_20260702_019_moomoo_capital_flow_accumulation.json", trade_key="target_trades_by_window", ineligible_reason="paper_snapshot_disabled"),
    _spec("core_drawdown_flow_put_stabilization_paper_sleeve", "CORE_DRAWDOWN_FLOW_PUT_STABILIZATION_PAPER", "core_drawdown_flow_put_stabilization_top1_v1", artifact="data/experiments/exp-20260723-004/exp_20260723_004_core_drawdown_flow_put_observer.json", ineligible_reason="canonical classic replay has zero rows; owner-assumed options backfill is research-only"),
    _spec("finra_ats_share_paper_sleeve", "FINRA_ATS_DARK_SHARE_RISE_PAPER", "finra_ats_weekly_dark_share_rise_top1_v1", paper_enabled=False, artifact="data/experiments/exp-20260703-016/exp_20260703_016_finra_ats_weekly_dark_share.json", trade_key="target_trades_by_window", ineligible_reason="paper_snapshot_disabled"),
    _spec("finra_otc_internalization_paper_sleeve", "FINRA_OTC_INTERNALIZATION_RETREAT_PAPER", "finra_otc_internalization_retreat_top1_v1", paper_enabled=False, artifact="data/experiments/exp-20260706-018/exp_20260706_018_finra_otc_internalization_retreat.json", trade_key="target_trades_by_window", ineligible_reason="paper_snapshot_disabled"),
)


def _parent_child_edges(parent: str, children: Iterable[str]) -> tuple[frozenset[str], ...]:
    return tuple(frozenset((parent, child)) for child in children)


CONFLICT_EDGES = (
    *_parent_child_edges(
        "event_sleeve_bundle",
        (
            "form4_event_sleeve",
            "sec_negative_event_sleeve",
            "sec_governance_event_sleeve",
            "sec_leadership_event_sleeve",
            "sec_financial_report_event_sleeve",
        ),
    ),
    *_parent_child_edges(
        "accepted_helper_source_priority_allocator_paper_sleeve",
        (
            "free_data_cross_source_consensus_paper_sleeve",
            "volatility_relief_stock_leadership_paper_sleeve",
            "rolling_corr_peer_shock_paper_sleeve",
            "turn_of_month_liquid_leadership_paper_sleeve",
            "industry_relative_laggard_repair_paper_sleeve",
            "revision_surprise_low_extension_paper_sleeve",
            "narrow_range_compression_breakout_paper_sleeve",
            "industry_stable_core_flow_paper_sleeve",
        ),
    ),
    *_parent_child_edges(
        "accepted_source_consensus_paper_sleeve",
        (
            "alpha_score_market_regime_paper_sleeve",
            "finra_iwm_paper_sleeve",
            "volume_breadth_breakout_paper_sleeve",
        ),
    ),
    *_parent_child_edges(
        "free_data_cross_source_consensus_paper_sleeve",
        (
            "fundamental_growth_rs_paper_sleeve",
            "volume_breadth_breakout_paper_sleeve",
            "finra_iwm_paper_sleeve",
            "alpha_score_market_regime_paper_sleeve",
        ),
    ),
)


LEDGER_TO_SURFACE = {
    "accepted_helper_source_priority_allocator": "accepted_helper_source_priority_allocator_paper_sleeve",
    "accepted_source_consensus": "accepted_source_consensus_paper_sleeve",
    "alpha_score_market_regime": "alpha_score_market_regime_paper_sleeve",
    "broad_market": "broad_market_paper_sleeve",
    "distribution_day_absorption_leadership": "distribution_day_absorption_leadership_paper_sleeve",
    "finra_otc_internalization": "finra_otc_internalization_paper_sleeve",
    "free_data_cross_source_consensus": "free_data_cross_source_consensus_paper_sleeve",
    "fundamental_growth_rs": "fundamental_growth_rs_paper_sleeve",
    "industry_relative_laggard_repair": "industry_relative_laggard_repair_paper_sleeve",
    "low_deployment_etf": "low_deployment_etf_overlay",
    "moomoo_capital_flow": "moomoo_capital_flow_paper_sleeve",
    "revision_surprise_low_extension": "revision_surprise_low_extension_paper_sleeve",
    "sec_financial_report": "sec_financial_report_event_sleeve",
    "sec_governance": "sec_governance_event_sleeve",
    "sec_leadership": "sec_leadership_event_sleeve",
    "sec_negative": "sec_negative_event_sleeve",
    "state_surface": "state_surface_sleeve",
    "supplier_financing_debt_relief": "supplier_financing_debt_relief_paper_sleeve",
    "turn_of_month_liquid_leadership": "turn_of_month_liquid_leadership_paper_sleeve",
    "volatility_contraction": "volatility_contraction_paper_sleeve",
    "volume_breadth_breakout": "volume_breadth_breakout_paper_sleeve",
}


def _repo_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _read_json(path: str | Path) -> Any:
    return json.loads(_repo_path(path).read_text(encoding="utf-8"))


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with _repo_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: str | Path, value: Any) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(_serial(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _serial(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serial(item) for item in value]
    if isinstance(value, (np.floating, float)):
        return round(float(value), 12)
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def validate_inventory() -> dict[str, Any]:
    if len(SURFACE_SPECS) != 41:
        raise ValueError(f"expected 41 surface specs, found {len(SURFACE_SPECS)}")
    names = [row["surface"] for row in SURFACE_SPECS]
    if len(set(names)) != len(names):
        raise ValueError("duplicate surface specs")
    actual_snapshot_hash = _sha256_file(SNAPSHOT_PATH)
    if actual_snapshot_hash != SNAPSHOT_SHA256:
        raise ValueError("latest quant snapshot identity changed")
    payload = _read_json(SNAPSHOT_PATH)
    rows = payload["paper_sleeve_execution_contract"]["surfaces"]
    actual = [(row["surface"], row["sleeve"], bool(row["paper_enabled"])) for row in rows]
    expected = [(row["surface"], row["sleeve"], bool(row["paper_enabled"])) for row in SURFACE_SPECS]
    if actual != expected:
        raise ValueError("41-surface identity/order differs from the frozen execution contract")
    return {
        "path": SNAPSHOT_PATH.as_posix(),
        "sha256": actual_snapshot_hash,
        "surface_count": len(rows),
        "paper_enabled_count": sum(int(row[2]) for row in actual),
        "paper_disabled_count": sum(int(not row[2]) for row in actual),
    }


def _normalize_trade(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    if value.get("paper_notional_usd") is None:
        value["paper_notional_usd"] = value.get("notional_usd")
    return value


def _surface_trade_rows(spec: Mapping[str, Any], calendars: Mapping[str, Sequence[date]]) -> dict[str, list[dict[str, Any]]]:
    payload = _read_json(str(spec["artifact"]))
    key = str(spec["trade_key"])
    if key == "all_trades_by_entry_window":
        source = payload.get("trades") or []
        result: dict[str, list[dict[str, Any]]] = {}
        for window in WINDOWS:
            first, last = calendars[window][0], calendars[window][-1]
            result[window] = [
                _normalize_trade(row)
                for row in source
                if first <= date.fromisoformat(str(row["entry_date"])[:10]) <= last
            ]
        return result
    surface = payload.get(key)
    if not isinstance(surface, Mapping):
        raise ValueError(f"missing {key}")
    return {window: [_normalize_trade(row) for row in surface.get(window, [])] for window in WINDOWS}


def reconstruct_surfaces() -> dict[str, Any]:
    inventory_identity = validate_inventory()
    if _sha256_file(OHLCV_PATH) != OHLCV_SHA256:
        raise ValueError("frozen OHLCV identity changed")
    core_payloads, calendars, core_returns, core_identity = reassess.load_active_core()
    ohlcv_rows, ohlcv_identity = reassess._load_ohlcv_snapshot(
        OHLCV_PATH,
        expected_experiment_id="exp-20260716-011",
        expected_gzip_sha256=OHLCV_SHA256,
    )
    price_map = pc._price_map_from_rows(ohlcv_rows)
    returns: dict[str, dict[str, np.ndarray]] = {}
    contributions: dict[str, list[tuple[str, float]]] = {}
    inventory: list[dict[str, Any]] = []
    artifact_hashes: dict[str, str] = {}

    for raw_spec in SURFACE_SPECS:
        spec = dict(raw_spec)
        artifact = spec.get("artifact")
        if artifact and _repo_path(artifact).exists():
            artifact_hashes[str(artifact)] = _sha256_file(str(artifact))
        row = {
            **spec,
            "classic_eligible": False,
            "classic_ineligible_reason": spec.get("preflight_ineligible_reason"),
            "classic_trade_counts": {window: 0 for window in WINDOWS},
        }
        if not spec["paper_enabled"]:
            row["classic_ineligible_reason"] = "paper_snapshot_disabled"
            inventory.append(row)
            continue
        if not artifact or not spec.get("trade_key"):
            inventory.append(row)
            continue
        try:
            surface = _surface_trade_rows(spec, calendars)
            by_window: dict[str, np.ndarray] = {}
            surface_contributions: list[tuple[str, float]] = []
            diagnostics: dict[str, Any] = {}
            for window in WINDOWS:
                if not surface[window]:
                    raise ValueError(f"zero current-rule trades in {window}")
                allocation = pc.allocate_sleeve_capital(
                    surface[window],
                    calendars[window],
                    sleeve_capital=RECONSTRUCTION_CAPITAL_USD,
                    price_map=price_map,
                )
                if not allocation.get("cash_nonnegative") or not allocation.get("ending_all_positions_settled"):
                    raise ValueError(f"cash/settlement failure in {window}")
                pnl_by_day: defaultdict[date, float] = defaultdict(float)
                usable = 0
                unusable = 0
                for trade in allocation["allocated_rows"]:
                    daily, diagnostic = pc.reconstruct_trade_daily_pnl(trade, calendars[window], price_map)
                    if not diagnostic.get("usable"):
                        unusable += 1
                        continue
                    usable += 1
                    surface_contributions.append((str(diagnostic["ticker"]), float(diagnostic["net_pnl"])))
                    for day, pnl in daily.items():
                        pnl_by_day[day] += float(pnl)
                if unusable or usable != len(allocation["allocated_rows"]):
                    raise ValueError(f"incomplete MTM reconstruction in {window}: usable={usable}, unusable={unusable}")
                by_window[window] = pc.pnl_to_returns(pnl_by_day, calendars[window], initial_capital=RECONSTRUCTION_CAPITAL_USD)
                diagnostics[window] = {
                    "source_trade_count": len(surface[window]),
                    "allocated_trade_count": len(allocation["allocated_rows"]),
                    "usable_trade_count": usable,
                    "min_cash_usd": float(allocation["min_cash_usd"]),
                }
            returns[str(spec["surface"])] = by_window
            contributions[str(spec["surface"])] = surface_contributions
            row["classic_eligible"] = True
            row["classic_ineligible_reason"] = None
            row["classic_trade_counts"] = {window: len(surface[window]) for window in WINDOWS}
            row["reconstruction"] = diagnostics
        except Exception as exc:  # fail closed and retain the surface identity
            row["classic_ineligible_reason"] = f"runtime_reconstruction_failed:{type(exc).__name__}:{exc}"
        inventory.append(row)

    return {
        "core_payloads": core_payloads,
        "calendars": calendars,
        "core_returns": core_returns,
        "surface_returns": returns,
        "surface_contributions": contributions,
        "inventory": inventory,
        "input_identity": {
            "paper_contract": inventory_identity,
            "core": core_identity,
            "ohlcv": ohlcv_identity,
            "artifact_hashes": dict(sorted(artifact_hashes.items())),
        },
    }


def has_overlap(support: Iterable[str]) -> bool:
    selected = set(support)
    return any(edge <= selected for edge in CONFLICT_EDGES)


def enumerate_coarse_allocations(eligible: Sequence[str]) -> Iterable[dict[str, float]]:
    names = tuple(sorted(eligible))
    yield {}
    for count in range(1, min(MAX_ACTIVE_SURFACES, len(names)) + 1):
        for support in itertools.combinations(names, count):
            if has_overlap(support):
                continue
            for values in itertools.product(COARSE_LEVELS, repeat=count):
                if sum(values) <= TOTAL_PAPER_CAP + 1e-12:
                    yield dict(zip(support, values))


def enumerate_refined_allocations(support: Sequence[str]) -> Iterable[dict[str, float]]:
    names = tuple(sorted(support))
    if not names:
        yield {}
        return
    levels = tuple(round(index * REFINED_STEP, 10) for index in range(round(SURFACE_CAP / REFINED_STEP) + 1))
    for values in itertools.product(levels, repeat=len(names)):
        weights = {name: value for name, value in zip(names, values) if value > 0.0}
        if sum(weights.values()) <= TOTAL_PAPER_CAP + 1e-12 and not has_overlap(weights):
            yield weights


def _metric_delta(after: Mapping[str, Any], before: Mapping[str, Any]) -> dict[str, float]:
    keys = ("total_return_fraction", "total_pnl", "sharpe_daily", "expected_value_score", "max_drawdown_pct", "expected_shortfall_95")
    return {key: float(after[key]) - float(before[key]) for key in keys}


def evaluate_allocation(
    weights: Mapping[str, float],
    *,
    labels: Sequence[str],
    core_returns: Mapping[str, np.ndarray],
    surface_returns: Mapping[str, Mapping[str, np.ndarray]],
) -> dict[str, Any]:
    active = {str(key): float(value) for key, value in weights.items() if float(value) > 0.0}
    if len(active) > MAX_ACTIVE_SURFACES or has_overlap(active):
        raise ValueError("allocation violates active-count or overlap constraints")
    if any(name not in surface_returns for name in active):
        raise ValueError("allocation references an ineligible surface")
    if any(value > SURFACE_CAP + 1e-12 for value in active.values()):
        raise ValueError("surface cap exceeded")
    paper_weight = sum(active.values())
    if paper_weight > TOTAL_PAPER_CAP + 1e-12:
        raise ValueError("total paper cap exceeded")

    windows: dict[str, Any] = {}
    objective = 0.0
    aggregate_ev_delta = 0.0
    aggregate_pnl_delta = 0.0
    material_regressions = 0
    max_dd_worsening = -math.inf
    max_es_worsening = -math.inf
    for label in labels:
        core = np.asarray(core_returns[label], dtype=float)
        combined = (1.0 - paper_weight) * core
        for name, weight in active.items():
            combined = combined + weight * np.asarray(surface_returns[name][label], dtype=float)
        before = reassess.current_return_metrics(core)
        after = reassess.current_return_metrics(combined)
        delta = _metric_delta(after, before)
        objective += float(after["expected_value_score"])
        aggregate_ev_delta += delta["expected_value_score"]
        aggregate_pnl_delta += delta["total_pnl"]
        material = delta["expected_value_score"] < -0.01 * abs(float(before["expected_value_score"])) and delta["total_pnl"] < 0.0
        material_regressions += int(material)
        dd_worsening = delta["max_drawdown_pct"]
        before_es = float(before["expected_shortfall_95"])
        after_es = float(after["expected_shortfall_95"])
        es_worsening = (after_es - before_es) / before_es if before_es > 0.0 else (0.0 if after_es <= 0.0 else math.inf)
        max_dd_worsening = max(max_dd_worsening, dd_worsening)
        max_es_worsening = max(max_es_worsening, es_worsening)
        windows[label] = {"core_metrics": before, "combined_metrics": after, "delta_vs_core": delta, "material_regression": material, "es95_worsening_fraction": es_worsening}
    checks = {
        "non_null": paper_weight > 0.0,
        "positive_aggregate_ev": aggregate_ev_delta > 0.0,
        "positive_aggregate_pnl": aggregate_pnl_delta > 0.0,
        "material_regressions_at_most_one": material_regressions <= 1,
        "drawdown_worsening_at_most_0p5pp": max_dd_worsening <= 0.005,
        "es95_worsening_at_most_5pct": max_es_worsening <= 0.05,
        "capital_neutral": paper_weight <= TOTAL_PAPER_CAP + 1e-12,
        "surface_caps": all(value <= SURFACE_CAP + 1e-12 for value in active.values()),
        "max_four_active": len(active) <= MAX_ACTIVE_SURFACES,
        "overlap_excluded": not has_overlap(active),
    }
    return {
        "weights": dict(sorted(active.items())),
        "core_weight": 1.0 - paper_weight,
        "paper_weight": paper_weight,
        "objective_ev_sum": objective,
        "aggregate_ev_delta": aggregate_ev_delta,
        "aggregate_pnl_delta": aggregate_pnl_delta,
        "material_regression_count": material_regressions,
        "max_drawdown_worsening": max_dd_worsening,
        "max_es95_worsening_fraction": max_es_worsening,
        "checks": checks,
        "feasible": all(checks.values()),
        "windows": windows,
    }


def _rank_key(result: Mapping[str, Any]) -> tuple[Any, ...]:
    return (-float(result["objective_ev_sum"]), -float(result["aggregate_pnl_delta"]), float(result["paper_weight"]), tuple(sorted(result["weights"].items())))


def optimize_allocations(
    allocations: Iterable[Mapping[str, float]],
    *,
    labels: Sequence[str],
    core_returns: Mapping[str, np.ndarray],
    surface_returns: Mapping[str, Mapping[str, np.ndarray]],
) -> dict[str, Any]:
    scanned = 0
    feasible = 0
    best_feasible: dict[str, Any] | None = None
    best_nonzero: dict[str, Any] | None = None
    best_pnl_nonzero: dict[str, Any] | None = None
    null_result: dict[str, Any] | None = None
    failed_check_counts: defaultdict[str, int] = defaultdict(int)
    positive_ev_count = 0
    positive_pnl_count = 0
    positive_ev_and_pnl_count = 0
    for weights in allocations:
        result = evaluate_allocation(weights, labels=labels, core_returns=core_returns, surface_returns=surface_returns)
        scanned += 1
        if not result["weights"]:
            null_result = result
        else:
            if best_nonzero is None or _rank_key(result) < _rank_key(best_nonzero):
                best_nonzero = result
            pnl_rank = (
                -float(result["aggregate_pnl_delta"]),
                -float(result["aggregate_ev_delta"]),
                float(result["paper_weight"]),
                tuple(sorted(result["weights"].items())),
            )
            if best_pnl_nonzero is None:
                best_pnl_nonzero = result
            else:
                incumbent_rank = (
                    -float(best_pnl_nonzero["aggregate_pnl_delta"]),
                    -float(best_pnl_nonzero["aggregate_ev_delta"]),
                    float(best_pnl_nonzero["paper_weight"]),
                    tuple(sorted(best_pnl_nonzero["weights"].items())),
                )
                if pnl_rank < incumbent_rank:
                    best_pnl_nonzero = result
            positive_ev = result["aggregate_ev_delta"] > 0.0
            positive_pnl = result["aggregate_pnl_delta"] > 0.0
            positive_ev_count += int(positive_ev)
            positive_pnl_count += int(positive_pnl)
            positive_ev_and_pnl_count += int(positive_ev and positive_pnl)
            for check, passed in result["checks"].items():
                if not passed:
                    failed_check_counts[str(check)] += 1
        if result["feasible"]:
            feasible += 1
            if best_feasible is None or _rank_key(result) < _rank_key(best_feasible):
                best_feasible = result
    if null_result is None:
        null_result = evaluate_allocation({}, labels=labels, core_returns=core_returns, surface_returns=surface_returns)
    return {
        "scanned_vector_count": scanned,
        "feasible_vector_count": feasible,
        "best_feasible": best_feasible,
        "best_nonzero_unconstrained": best_nonzero,
        "best_pnl_nonzero": best_pnl_nonzero,
        "positive_ev_nonzero_count": positive_ev_count,
        "positive_pnl_nonzero_count": positive_pnl_count,
        "positive_ev_and_pnl_nonzero_count": positive_ev_and_pnl_count,
        "failed_check_counts": dict(sorted(failed_check_counts.items())),
        "selected": best_feasible or null_result,
        "fallback_to_100pct_core": best_feasible is None,
    }


def _walk_forward(core_returns: Mapping[str, np.ndarray], surface_returns: Mapping[str, Mapping[str, np.ndarray]]) -> list[dict[str, Any]]:
    eligible = tuple(sorted(surface_returns))
    folds = [(("old_thin",), "mid_weak"), (("old_thin", "mid_weak"), "late_strong")]
    results: list[dict[str, Any]] = []
    for train, test in folds:
        coarse = optimize_allocations(enumerate_coarse_allocations(eligible), labels=train, core_returns=core_returns, surface_returns=surface_returns)
        support = tuple(coarse["selected"]["weights"])
        refined = optimize_allocations(enumerate_refined_allocations(support), labels=train, core_returns=core_returns, surface_returns=surface_returns)
        selected = refined["selected"]
        oos = evaluate_allocation(selected["weights"], labels=(test,), core_returns=core_returns, surface_returns=surface_returns)
        results.append({"train_windows": list(train), "test_window": test, "coarse_search": coarse, "refined_search": refined, "oos_result": oos, "passed": bool(selected["weights"]) and bool(oos["feasible"])})
    return results


def recent_surface_diagnostics() -> dict[str, Any]:
    actual_hash = _sha256_file(FORWARD_PATH)
    if actual_hash != FORWARD_SHA256:
        raise ValueError("forward replacement ledger identity changed")
    rows = [json.loads(line) for line in _repo_path(FORWARD_PATH).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 196 or len({row["decision_id"] for row in rows}) != len(rows):
        raise ValueError("expected 196 unique settled forward decisions")
    unknown = sorted({str(row["sleeve_key"]) for row in rows} - set(LEDGER_TO_SURFACE))
    if unknown:
        raise ValueError(f"unmapped recent sleeves: {unknown}")
    totals: defaultdict[str, dict[str, float]] = defaultdict(lambda: {"rows": 0.0, "notional": 0.0, "cash": 0.0, "spy": 0.0, "qqq": 0.0})
    dates: list[str] = []
    for row in rows:
        surface = LEDGER_TO_SURFACE[str(row["sleeve_key"])]
        item = totals[surface]
        item["rows"] += 1.0
        item["notional"] += float(row["notional_usd"])
        item["cash"] += float(row["replacement_value_vs_cash_usd"])
        item["spy"] += float(row["replacement_value_vs_spy_usd"])
        item["qqq"] += float(row["replacement_value_vs_qqq_usd"])
        dates.extend((str(row["entry_date"]), str(row["exit_date"])))
    enabled = {row["surface"]: bool(row["paper_enabled"]) for row in SURFACE_SPECS}
    diagnostics: dict[str, Any] = {}
    returns: dict[str, dict[str, float]] = {}
    for spec in SURFACE_SPECS:
        name = str(spec["surface"])
        item = totals.get(name)
        row_count = int(item["rows"]) if item else 0
        notional = float(item["notional"]) if item else 0.0
        eligible = bool(enabled[name] and row_count >= MIN_RECENT_SETTLED_ROWS and notional > 0.0)
        values = {key: (float(item[key]) / notional if item and notional > 0.0 else None) for key in ("cash", "spy", "qqq")}
        diagnostics[name] = {"row_count": row_count, "notional_usd": notional, "paper_enabled": enabled[name], "recent_eligible": eligible, "return_vs_cash": values["cash"], "return_vs_spy": values["spy"], "return_vs_qqq": values["qqq"]}
        if eligible:
            returns[name] = values
    return {"path": FORWARD_PATH.as_posix(), "sha256": actual_hash, "period": {"start": min(dates), "end": max(dates)}, "row_count": len(rows), "covered_surface_count": len(totals), "eligible_surface_count": len(returns), "surfaces": diagnostics, "returns": returns}


def optimize_recent(recent: Mapping[str, Any]) -> dict[str, Any]:
    returns = recent["returns"]
    scanned = 0
    feasible = 0
    best: dict[str, Any] | None = None
    null: dict[str, Any] | None = None
    for weights in enumerate_coarse_allocations(tuple(returns)):
        contributions = {comparator: sum(float(weight) * float(returns[name][comparator]) for name, weight in weights.items()) for comparator in ("cash", "spy", "qqq")}
        result = {"weights": dict(sorted(weights.items())), "core_weight": 1.0 - sum(weights.values()), "paper_weight": sum(weights.values()), "weighted_return_vs_cash": contributions["cash"], "weighted_return_vs_spy": contributions["spy"], "weighted_return_vs_qqq": contributions["qqq"], "inferred_value_usd": {key: PORTFOLIO_CAPITAL_USD * value for key, value in contributions.items()}, "feasible": bool(weights) and all(value > 0.0 for value in contributions.values())}
        scanned += 1
        if not weights:
            null = result
        if result["feasible"]:
            feasible += 1
            rank = (-result["weighted_return_vs_cash"], -result["weighted_return_vs_spy"], -result["weighted_return_vs_qqq"], result["paper_weight"], tuple(result["weights"].items()))
            if best is None or rank < best["_rank"]:
                best = {**result, "_rank": rank}
    if best is not None:
        best.pop("_rank", None)
    return {"scanned_vector_count": scanned, "feasible_vector_count": feasible, "selected": best or null, "fallback_to_100pct_core": best is None, "interpretation": "descriptive hindsight over settled rows; never an activation gate by itself"}


def selected_recent_check(weights: Mapping[str, float], recent: Mapping[str, Any]) -> dict[str, Any]:
    support = list(weights)
    missing = [name for name in support if name not in recent["returns"]]
    contributions = {comparator: sum(float(weight) * float(recent["returns"][name][comparator]) for name, weight in weights.items() if name in recent["returns"]) for comparator in ("cash", "spy", "qqq")}
    return {"support_coverage_complete": not missing, "missing_surfaces": missing, "weighted_return": contributions, "inferred_value_usd": {key: PORTFOLIO_CAPITAL_USD * value for key, value in contributions.items()}, "nonnegative_vs_all": not missing and all(value >= 0.0 for value in contributions.values())}


def write_coarse_combination_manifest(
    path: str | Path,
    *,
    eligible: Sequence[str],
    core_returns: Mapping[str, np.ndarray],
    surface_returns: Mapping[str, Mapping[str, np.ndarray]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    active_counts: Counter[int] = Counter()
    weight_patterns: Counter[str] = Counter()
    supports: defaultdict[int, set[tuple[str, ...]]] = defaultdict(set)
    vector_digest = hashlib.sha256()
    for index, weights in enumerate(enumerate_coarse_allocations(eligible)):
        result = evaluate_allocation(
            weights,
            labels=WINDOWS,
            core_returns=core_returns,
            surface_returns=surface_returns,
        )
        support = tuple(sorted(weights))
        pattern = "+".join(
            f"{100.0 * value:.1f}%" for value in sorted(weights.values())
        ) or "null"
        active_counts[len(weights)] += 1
        weight_patterns[pattern] += 1
        supports[len(weights)].add(support)
        canonical = (
            json.dumps(
                dict(sorted(weights.items())),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        vector_digest.update(canonical.encode("utf-8"))
        rows.append(
            {
                "combination_id": f"coarse-{index:05d}",
                "weights": dict(sorted(weights.items())),
                "core_weight": result["core_weight"],
                "paper_weight": result["paper_weight"],
                "aggregate_ev_delta": result["aggregate_ev_delta"],
                "aggregate_pnl_delta": result["aggregate_pnl_delta"],
                "material_regression_count": result["material_regression_count"],
                "max_drawdown_worsening": result["max_drawdown_worsening"],
                "max_es95_worsening_fraction": result["max_es95_worsening_fraction"],
                "feasible": result["feasible"],
                "failed_checks": sorted(
                    key for key, passed in result["checks"].items() if not passed
                ),
            }
        )
    _write_jsonl(path, rows)
    return {
        "path": str(Path(path).as_posix()),
        "sha256": _sha256_file(path),
        "vector_identity_sha256": vector_digest.hexdigest(),
        "total_vector_count": len(rows),
        "nonnull_vector_count": len(rows) - 1,
        "vectors_by_active_surface_count": {
            str(key): value for key, value in sorted(active_counts.items())
        },
        "unique_supports_by_active_surface_count": {
            str(key): len(value) for key, value in sorted(supports.items())
        },
        "vectors_by_weight_pattern": dict(sorted(weight_patterns.items())),
        "eligible_surfaces": list(sorted(eligible)),
        "pairwise_conflict_edges": [sorted(edge) for edge in CONFLICT_EDGES],
    }


def ticker_concentration(weights: Mapping[str, float], reconstructed: Mapping[str, Any]) -> dict[str, Any]:
    paper_weight = sum(float(value) for value in weights.values())
    rows: list[tuple[str, float]] = []
    for window in WINDOWS:
        for trade in reconstructed["core_payloads"][window].get("trades") or []:
            ticker = str(trade.get("ticker") or "").strip().upper()
            pnl = reassess._finite(trade.get("pnl"))
            if ticker and pnl is not None:
                rows.append((ticker, (1.0 - paper_weight) * pnl))
    for surface, weight in weights.items():
        scale = float(weight) * PORTFOLIO_CAPITAL_USD / RECONSTRUCTION_CAPITAL_USD
        rows.extend((ticker, scale * pnl) for ticker, pnl in reconstructed["surface_contributions"][surface])
    result = pc._concentration(rows)
    result["checks"] = {
        "single_ticker_positive_share_at_most_50pct": result["single_ticker_positive_share"] is not None and float(result["single_ticker_positive_share"]) <= 0.50,
        "top_5_contribution_at_most_60pct": result["top_5_contribution_pct"] is not None and float(result["top_5_contribution_pct"]) <= 0.60,
        "hhi_at_most_0p35": result["hhi_concentration"] is not None and float(result["hhi_concentration"]) <= 0.35,
    }
    result["passed"] = all(result["checks"].values())
    return result


def _expanded_weights(weights: Mapping[str, float]) -> dict[str, float]:
    return {str(spec["surface"]): float(weights.get(str(spec["surface"]), 0.0)) for spec in SURFACE_SPECS}


def run(output_dir: str | Path, *, experiment_id: str = EXPERIMENT_ID) -> dict[str, Any]:
    reconstructed = reconstruct_surfaces()
    surface_returns = reconstructed["surface_returns"]
    eligible = tuple(sorted(surface_returns))
    coarse = optimize_allocations(enumerate_coarse_allocations(eligible), labels=WINDOWS, core_returns=reconstructed["core_returns"], surface_returns=surface_returns)
    if coarse["selected"]["weights"]:
        refinement_support = tuple(coarse["selected"]["weights"])
        refinement_basis = "coarse_best_feasible_support"
    else:
        refinement_support = tuple(
            sorted(
                set((coarse["best_nonzero_unconstrained"] or {}).get("weights", {}))
                | set((coarse["best_pnl_nonzero"] or {}).get("weights", {}))
            )
        )
        refinement_basis = "union_of_coarse_ev_and_pnl_frontier_supports"
    refined = optimize_allocations(enumerate_refined_allocations(refinement_support), labels=WINDOWS, core_returns=reconstructed["core_returns"], surface_returns=surface_returns)
    classic_selected = refined["selected"]
    walk_forward = _walk_forward(reconstructed["core_returns"], surface_returns)
    recent = recent_surface_diagnostics()
    recent_search = optimize_recent(recent)
    recent_check = selected_recent_check(classic_selected["weights"], recent)
    concentration = ticker_concentration(classic_selected["weights"], reconstructed)
    single_surface_diagnostics = {}
    for surface in eligible:
        diagnostic = evaluate_allocation({surface: SURFACE_CAP}, labels=WINDOWS, core_returns=reconstructed["core_returns"], surface_returns=surface_returns)
        single_surface_diagnostics[surface] = {
            "weight": SURFACE_CAP,
            "aggregate_ev_delta": diagnostic["aggregate_ev_delta"],
            "aggregate_pnl_delta": diagnostic["aggregate_pnl_delta"],
            "material_regression_count": diagnostic["material_regression_count"],
            "max_drawdown_worsening": diagnostic["max_drawdown_worsening"],
            "max_es95_worsening_fraction": diagnostic["max_es95_worsening_fraction"],
            "checks": diagnostic["checks"],
            "feasible": diagnostic["feasible"],
        }
    robust_nonnull = bool(classic_selected["weights"]) and bool(classic_selected["feasible"]) and all(row["passed"] for row in walk_forward) and bool(recent_check["nonnegative_vs_all"]) and bool(concentration["passed"])
    recommended_weights = dict(classic_selected["weights"]) if robust_nonnull else {}
    recommended = evaluate_allocation(recommended_weights, labels=WINDOWS, core_returns=reconstructed["core_returns"], surface_returns=surface_returns)
    inventory = []
    for row in reconstructed["inventory"]:
        recent_row = recent["surfaces"][row["surface"]]
        inventory.append({**row, "recent": recent_row, "forced_zero_in_recommendation": row["surface"] not in recommended_weights})
    identity_checks = {
        "surface_count_is_41": len(inventory) == 41,
        "surface_identity_unique": len({row["surface"] for row in inventory}) == 41,
        "snapshot_order_exact": [row["surface"] for row in inventory] == [row["surface"] for row in SURFACE_SPECS],
        "all_surfaces_have_rule_version": all(bool(row["rule_version"]) for row in inventory),
        "all_surfaces_have_classic_eligibility_reason_or_path": all(row["classic_eligible"] or bool(row["classic_ineligible_reason"]) for row in inventory),
        "all_surfaces_have_recent_coverage_status": all("recent" in row for row in inventory),
        "disabled_surfaces_forced_zero": all(not row["classic_eligible"] for row in inventory if not row["paper_enabled"]),
        "overlap_excluded": not has_overlap(recommended_weights),
    }
    measurement_passed = all(identity_checks.values())
    allocation_decision = "observed_only_nonnull" if robust_nonnull else "rejected_keep_100pct_core"
    output = _repo_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "coarse_combination_manifest.jsonl"
    combination_manifest = write_coarse_combination_manifest(
        manifest_path,
        eligible=eligible,
        core_returns=reconstructed["core_returns"],
        surface_returns=surface_returns,
    )
    if int(combination_manifest["total_vector_count"]) != int(coarse["scanned_vector_count"]):
        raise ValueError("coarse search and manifest vector counts differ")
    result = {
        "schema": "ginger.current_paper_core_allocator.v2",
        "experiment_id": experiment_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "measurement_decision": "accepted_measurement_repair" if measurement_passed else "rejected_measurement_repair",
        "allocation_decision": allocation_decision,
        "result_ceiling": "observed_only",
        "trade_enabled": False,
        "production_changed": False,
        "selection_contract": {"registered_surface_count": 41, "current_rule_only": True, "classic_windows": list(WINDOWS), "coarse_weight_levels": list(COARSE_LEVELS), "refined_step": REFINED_STEP, "total_paper_cap": TOTAL_PAPER_CAP, "surface_cap": SURFACE_CAP, "max_active_surfaces": MAX_ACTIVE_SURFACES, "null_core_admissible": True, "recent_min_settled_rows": MIN_RECENT_SETTLED_ROWS, "recent_use": "descriptive contradiction check only"},
        "input_identity": {**reconstructed["input_identity"], "forward_ledger": {key: recent[key] for key in ("path", "sha256", "period", "row_count")}},
        "surface_inventory": inventory,
        "inventory_summary": {"registered": 41, "paper_enabled": sum(int(row["paper_enabled"]) for row in inventory), "paper_disabled": sum(int(not row["paper_enabled"]) for row in inventory), "classic_eligible": sum(int(row["classic_eligible"]) for row in inventory), "classic_forced_zero": sum(int(not row["classic_eligible"]) for row in inventory), "recent_covered": recent["covered_surface_count"], "recent_eligible": recent["eligible_surface_count"]},
        "identity_checks": identity_checks,
        "coarse_search": coarse,
        "coarse_combination_manifest": combination_manifest,
        "refinement_support": list(refinement_support),
        "refinement_basis": refinement_basis,
        "refined_search": refined,
        "classic_selected_allocation": {**classic_selected, "all_41_weights": _expanded_weights(classic_selected["weights"])},
        "walk_forward": walk_forward,
        "recent_surface_diagnostics": {key: value for key, value in recent.items() if key != "returns"},
        "recent_hindsight_search": recent_search,
        "classic_selected_recent_check": recent_check,
        "ticker_concentration": concentration,
        "single_surface_5pct_diagnostics": single_surface_diagnostics,
        "recommended_allocation": {**recommended, "all_41_weights": _expanded_weights(recommended_weights), "reason": "all evidence checks passed" if robust_nonnull else "fail-closed to core because one or more classic/walk-forward/recent/concentration checks failed"},
        "measurement_passed": measurement_passed,
        "robust_nonnull_allocation_passed": robust_nonnull,
        "limitations": ["Classic windows have been reused by prior experiments and are not untouched holdouts.", "Recent data is settled-trade replacement value, not a complete daily MTM covariance panel.", "A surface without a complete current-rule classic path is forced to zero rather than proxied by an older or sampled path.", "Six registered surfaces are forced to zero because the latest paper snapshot disables them.", "No result from this measurement changes production allocation or orders."],
    }
    full_path = output / "current_paper_core_allocator_result.json"
    _write_json(full_path, _serial(result))
    before_windows = {window: reassess.current_return_metrics(reconstructed["core_returns"][window]) for window in WINDOWS}
    after_windows = {window: recommended["windows"][window]["combined_metrics"] for window in WINDOWS}
    before = {"schema": "ginger.current_paper_core_allocator.measurement.v2", "experiment_id": experiment_id, "role": "before_100pct_active_core", "expected_value_score": sum(float(row["expected_value_score"]) for row in before_windows.values()), "total_pnl": sum(float(row["total_pnl"]) for row in before_windows.values()), "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in before_windows.values()), "total_trades": 49, "survival_rate": 0.8116, "benchmarks": {"strategy_total_return_pct": 100.0 * sum(float(row["total_return_fraction"]) for row in before_windows.values())}, "windows": before_windows}
    after = {"schema": "ginger.current_paper_core_allocator.measurement.v2", "experiment_id": experiment_id, "role": "after_recommended_allocation", "expected_value_score": sum(float(row["expected_value_score"]) for row in after_windows.values()), "total_pnl": sum(float(row["total_pnl"]) for row in after_windows.values()), "max_drawdown_pct": max(float(row["max_drawdown_pct"]) for row in after_windows.values()), "total_trades": 49, "survival_rate": 0.8116, "benchmarks": {"strategy_total_return_pct": 100.0 * sum(float(row["total_return_fraction"]) for row in after_windows.values())}, "windows": after_windows, "selected_weights": _expanded_weights(recommended_weights), "custom_gate_passed": robust_nonnull, "measurement_repair_passed": measurement_passed, "result_artifact": str(full_path.relative_to(REPO_ROOT)).replace("\\", "/")}
    _write_json(output / "before_measurement.json", _serial(before))
    _write_json(output / "after_measurement.json", _serial(after))
    summary = {"experiment_id": experiment_id, "measurement_decision": result["measurement_decision"], "allocation_decision": allocation_decision, "registered_surface_count": 41, "classic_eligible_count": result["inventory_summary"]["classic_eligible"], "recent_covered_count": recent["covered_surface_count"], "recent_eligible_count": recent["eligible_surface_count"], "coarse_vectors_scanned": coarse["scanned_vector_count"], "coarse_combination_manifest": combination_manifest, "coarse_positive_ev_count": coarse["positive_ev_nonzero_count"], "coarse_positive_pnl_count": coarse["positive_pnl_nonzero_count"], "coarse_positive_ev_and_pnl_count": coarse["positive_ev_and_pnl_nonzero_count"], "refinement_support": list(refinement_support), "refinement_basis": refinement_basis, "refined_vectors_scanned": refined["scanned_vector_count"], "refined_positive_ev_and_pnl_count": refined["positive_ev_and_pnl_nonzero_count"], "classic_selected_weights": classic_selected["weights"], "classic_selected_ev_delta": classic_selected["aggregate_ev_delta"], "classic_selected_pnl_delta": classic_selected["aggregate_pnl_delta"], "walk_forward_all_pass": all(row["passed"] for row in walk_forward), "classic_support_recent_check": recent_check, "recent_hindsight_weights": recent_search["selected"]["weights"] if recent_search["selected"] else {}, "recommended_weights": recommended_weights, "core_weight": recommended["core_weight"], "measurement_passed": measurement_passed, "robust_nonnull_allocation_passed": robust_nonnull, "result_artifact": str(full_path.relative_to(REPO_ROOT)).replace("\\", "/")}
    _write_json(output / "summary.json", _serial(summary))
    return _serial(summary)


def main(*, default_experiment_id: str = EXPERIMENT_ID) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", default=default_experiment_id)
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    output_dir = args.output_dir or f"data/experiments/{args.experiment_id}"
    print(json.dumps(run(output_dir, experiment_id=args.experiment_id), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
