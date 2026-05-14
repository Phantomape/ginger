"""
Report Generator: Produce a daily trade report.

Example output:

  ============================================================
  QUANT TRADING REPORT  —  2026-03-12 08:30
  ============================================================

  MARKET REGIME: BULL
    SPY 569.4 > 200MA 537.2 (+6.0%) | QQQ 483.1 > 200MA 462.0 (+4.6%)

  PORTFOLIO HEAT: 4.1%  (OK to add)

  ------------------------------------------------------------
  TOP TRADE CANDIDATES
  ------------------------------------------------------------

  1. NVDA
     Strategy:    trend_long
     Entry:       $920.00
     Stop:        $895.00  |  Target: $957.50
     R:R:         1.5:1
     Confidence:  0.78
     Sizing:      15 shares  ($13,800)
     Conditions:  above_200ma=True, breakout_20d=True, volume_spike=True
  ...
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_daily_report(signals, features_dict=None, portfolio_heat=None,
                           metrics=None, market_regime=None, open_positions=None,
                           dropped_signals=None, addon_actions=None,
                           entry_execution_plan=None,
                           pilot_attribution=None,
                           ai_infra_aggressive_attribution=None,
                           form4_event_queue=None,
                           form4_event_sleeve=None,
                           sec_event_queue=None,
                           sec_negative_event_sleeve=None,
                           sec_governance_event_queue=None,
                           sec_governance_event_sleeve=None,
                           sec_leadership_event_queue=None,
                           sec_leadership_event_sleeve=None,
                           sec_financial_report_t1_queue=None,
                           sec_financial_report_event_sleeve=None,
                           event_sleeve_bundle=None,
                           state_surface_sleeve=None,
                           low_deployment_etf_overlay=None,
                           space_catalyst_shadow=None,
                           space_catalyst_observation_slot=None,
                           space_catalyst_event_ledger=None,
                           platform_rs20_watch=None,
                           sec_10k_forward_watch=None,
                           non_ohlcv_snapshot=None,
                           crypto_sleeve=None):
    """
    Build a human-readable daily trade report string.

    Args:
        signals          (list[dict]):  Enriched, sized signals
        features_dict    (dict):        {ticker: features} for breakdown context
        portfolio_heat   (dict):        Output of portfolio_engine.compute_portfolio_heat()
        metrics          (dict):        Output of performance_engine.compute_metrics()
        market_regime    (dict):        Output of regime.compute_market_regime()
        open_positions   (dict):        Raw open_positions.json content
        dropped_signals  (list[dict]):  Signals dropped by risk_engine (ATR/R:R gates)
        addon_actions    (list[dict]):  Code-determined follow-through add-ons
        pilot_attribution (dict):       Pilot direct/replacement-value summary
        ai_infra_aggressive_attribution (dict): AI infra sleeve daily surface
        form4_event_queue (dict):       Default-off Form 4 observation queue
        form4_event_sleeve (dict):      Default-off Form 4 paper event sleeve
        sec_event_queue (dict):         Default-off SEC negative-reaction queue
        sec_negative_event_sleeve (dict): Default-off SEC negative-reaction paper sleeve
        sec_governance_event_queue (dict): Default-off SEC governance/procedural queue
        sec_governance_event_sleeve (dict): Default-off SEC governance paper sleeve
        sec_leadership_event_queue (dict): Default-off SEC leadership-change queue
        sec_leadership_event_sleeve (dict): Default-off SEC leadership paper sleeve
        sec_financial_report_t1_queue (dict): Default-off SEC financial-report T+1 queue
        sec_financial_report_event_sleeve (dict): Default-off SEC financial-report paper sleeve
        event_sleeve_bundle (dict):     Default-off aggregate event overlay attribution
        state_surface_sleeve (dict):    Default-off state-surface satellite paper sleeve
        low_deployment_etf_overlay (dict): Default-off low-deployment ETF paper overlay
        space_catalyst_shadow (dict):   Observe-only space catalyst candidate pool
        space_catalyst_observation_slot (dict): Observe-only blocked Space trade plan
        space_catalyst_event_ledger (dict): Observe-only Space event-state ledger
        platform_rs20_watch (dict):     Default-off platform RS20 no-gap watch ledger
        sec_10k_forward_watch (dict):   Default-off SEC 10-K liquidity watch ledger
        non_ohlcv_snapshot (dict):      Daily non-OHLCV coverage/catch-up status
        crypto_sleeve (dict):           Isolated BTC/USD sleeve advice

    Returns:
        str: Formatted report
    """
    lines = []
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("=" * 60)
    lines.append(f"QUANT TRADING REPORT  —  {now}")
    lines.append("=" * 60)

    # ── Market regime ───────────────────────────────────────────────────────
    if market_regime:
        regime = market_regime.get("regime", "UNKNOWN")
        note   = market_regime.get("note", "")
        lines.append(f"\nMARKET REGIME: {regime}")
        if note:
            lines.append(f"  {note}")

        # Per-index detail
        indices = market_regime.get("indices", {})
        for idx, info in indices.items():
            price  = info.get("close")
            ma200  = info.get("ma200")
            pct    = info.get("pct_from_ma")
            above  = info.get("above_ma")
            if price and ma200:
                sign = ">" if above else "<"
                lines.append(
                    f"  {idx}: {price:.1f} {sign} 200MA {ma200:.1f} "
                    f"({pct*100:+.1f}%)"
                )

    # ── Portfolio heat ──────────────────────────────────────────────────────
    if non_ohlcv_snapshot:
        status = non_ohlcv_snapshot.get("status")
        manifest = non_ohlcv_snapshot.get("coverage_manifest") or {}
        daily = manifest.get("daily_summary") or {}
        catchup = manifest.get("catchup_summary") or {}
        lines.append("\nNON-OHLCV DATA COVERAGE:")
        lines.append(f"  Daily snapshot: {status}")
        if daily:
            lines.append(
                "  Manifest daily: "
                f"generated={daily.get('days_generated')} "
                f"existing={daily.get('days_recorded_existing')} "
                f"failed={daily.get('days_failed')}"
            )
        if catchup:
            lines.append(
                "  Catch-up: "
                f"status={catchup.get('status')} "
                f"generated={catchup.get('days_generated')} "
                f"existing={catchup.get('days_recorded_existing')} "
                f"failed={catchup.get('days_failed')}"
            )
        estimate_revision = non_ohlcv_snapshot.get("estimate_revision_ledger") or {}
        if estimate_revision:
            lines.append(
                "  Estimate revisions: "
                f"rows={estimate_revision.get('row_count')} "
                f"usable={estimate_revision.get('estimate_revision_usable_rows')} "
                f"up={estimate_revision.get('up_revision_rows')} "
                f"down={estimate_revision.get('down_revision_rows')}"
            )

    if portfolio_heat:
        heat_pct = portfolio_heat.get("portfolio_heat_pct", 0)
        can_add  = portfolio_heat.get("can_add_new_positions", True)
        status   = "OK to add" if can_add else "CAPPED — no new trades"
        lines.append(f"\nPORTFOLIO HEAT: {heat_pct*100:.1f}%  ({status})")

    if crypto_sleeve:
        lines.append("\n" + "-" * 60)
        lines.append("BTC/USD CRYPTO SLEEVE")
        lines.append("-" * 60)
        if not crypto_sleeve.get("enabled", False):
            lines.append(
                "  Disabled/unavailable: "
                f"{crypto_sleeve.get('error') or crypto_sleeve.get('reason')}"
            )
        else:
            snapshot = crypto_sleeve.get("snapshot") or {}
            action = crypto_sleeve.get("action") or {}
            execution = crypto_sleeve.get("execution_notes") or {}
            target_pct = action.get("target_position_pct")
            current_pct = action.get("current_position_pct")
            target_text = (
                f"{target_pct * 100:.0f}%"
                if isinstance(target_pct, (int, float))
                else "n/a"
            )
            current_text = (
                f"{current_pct * 100:.0f}%"
                if isinstance(current_pct, (int, float))
                else "not configured"
            )
            trade_value = action.get("trade_value_usd")
            trade_text = (
                f"${abs(trade_value):,.0f}"
                if isinstance(trade_value, (int, float))
                else "manual sizing"
            )
            lines.append(
                f"  State:   {crypto_sleeve.get('state')}  |  "
                f"Action: {action.get('action')}  |  Target: {target_text}"
            )
            lines.append(
                f"  Current: {current_text}  |  Trade value: {trade_text}"
            )
            lines.append(
                f"  Price:   ${snapshot.get('close')}  |  "
                f"EMA20: ${snapshot.get('ema20')}  |  "
                f"EMA100: ${snapshot.get('ema100')}  |  "
                f"SMA200: ${snapshot.get('sma200')}"
            )
            lines.append(f"  Reason:  {crypto_sleeve.get('reason')}")
            if execution.get("preferred_signal_time"):
                lines.append(f"  Timing:  {execution['preferred_signal_time']}")
            if execution.get("reference_buy_limit") and execution.get("reference_sell_limit"):
                lines.append(
                    f"  Limit band: buy <= ${execution['reference_buy_limit']}, "
                    f"sell >= ${execution['reference_sell_limit']}"
                )

    if entry_execution_plan:
        slots = entry_execution_plan.get("available_slots")
        deferred = entry_execution_plan.get("deferred_breakout_signals") or []
        sliced = entry_execution_plan.get("slot_sliced_signals") or []
        lines.append(f"\nENTRY SLOTS: {slots} available")
        if deferred:
            tickers = ", ".join(d.get("ticker", "?") for d in deferred)
            lines.append(f"  Deferred breakout(s): {tickers}")
        if sliced:
            tickers = ", ".join(d.get("ticker", "?") for d in sliced)
            lines.append(f"  Slot-sliced candidate(s): {tickers}")

    if platform_rs20_watch and (
        platform_rs20_watch.get("candidate_count", 0) > 0
        or platform_rs20_watch.get("platform_missed_count", 0) > 0
    ):
        lines.append("\n" + "-" * 60)
        lines.append("PLATFORM RS20 NO-GAP WATCH")
        lines.append("-" * 60)
        persistence = platform_rs20_watch.get("persistence") or {}
        lines.append(
            f"  Trade enabled: {platform_rs20_watch.get('trade_enabled', False)}  |  "
            f"Missed platform: {platform_rs20_watch.get('platform_missed_count', 0)}  |  "
            f"RS20: {platform_rs20_watch.get('platform_rs20_missed_count', 0)}  |  "
            f"No-gap watch: {platform_rs20_watch.get('candidate_count', 0)}"
        )
        if persistence:
            lines.append(
                f"  Ledger rows: {persistence.get('ledger_row_count', 0)}  |  "
                f"Appended today: {persistence.get('appended_count', 0)}"
            )
        for candidate in (platform_rs20_watch.get("candidates") or [])[:5]:
            excess = candidate.get("excess_spy_return_20d")
            gap = candidate.get("gap_pct")
            excess_text = (
                f"{excess * 100:.1f}%"
                if isinstance(excess, (int, float))
                else "n/a"
            )
            gap_text = (
                f"{gap * 100:.1f}%"
                if isinstance(gap, (int, float))
                else "n/a"
            )
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"{candidate.get('decision', '?')} / {candidate.get('strategy', '?')} "
                f"RS20 excess {excess_text}, gap {gap_text} "
                "(observe only)"
            )

    if sec_10k_forward_watch and (
        sec_10k_forward_watch.get("candidate_count", 0) > 0
        or sec_10k_forward_watch.get("ten_k_event_count", 0) > 0
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC 10-K LIQUIDITY WATCH")
        lines.append("-" * 60)
        persistence = sec_10k_forward_watch.get("persistence") or {}
        lines.append(
            f"  Trade enabled: {sec_10k_forward_watch.get('trade_enabled', False)}  |  "
            f"10-K events: {sec_10k_forward_watch.get('ten_k_event_count', 0)}  |  "
            f"Outside universe: {sec_10k_forward_watch.get('outside_universe_10k_count', 0)}  |  "
            f"Liquidity qualified: {sec_10k_forward_watch.get('liquidity_qualified_count', 0)}  |  "
            f"Candidates: {sec_10k_forward_watch.get('candidate_count', 0)}"
        )
        if persistence:
            lines.append(
                f"  Ledger rows: {persistence.get('ledger_row_count', 0)}  |  "
                f"Appended today: {persistence.get('appended_count', 0)}"
            )
        if sec_10k_forward_watch.get("candidate_count", 0) == 0:
            status = (sec_10k_forward_watch.get("summary") or {}).get("by_status") or {}
            if status:
                status_text = ", ".join(f"{key}={value}" for key, value in sorted(status.items()))
                lines.append(f"  No watch candidate today: {status_text}")
        for candidate in (sec_10k_forward_watch.get("candidates") or [])[:5]:
            adv = candidate.get("avg_dollar_volume_20d")
            adv_text = (
                f"${adv / 1_000_000:.1f}M"
                if isinstance(adv, (int, float))
                else "n/a"
            )
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"{candidate.get('form_type', '10-K')} usable={candidate.get('usable_trade_date')} "
                f"ADV20={adv_text} {candidate.get('liquidity_bucket', 'adv_unknown')} "
                f"alts={candidate.get('same_day_core_alternative_count', 0)} "
                "(observe only)"
            )

    if space_catalyst_shadow and space_catalyst_shadow.get("candidate_count", 0) > 0:
        lines.append("\n" + "-" * 60)
        lines.append("SPACE CATALYST SHADOW UNIVERSE")
        lines.append("-" * 60)
        trade_enabled = space_catalyst_shadow.get("trade_enabled_tickers") or []
        lines.append(
            f"  Mode: {space_catalyst_shadow.get('mode', 'observe_only')}  |  "
            f"Candidates: {space_catalyst_shadow.get('candidate_count', 0)}  |  "
            f"Trade-enabled: {len(trade_enabled)}"
        )
        segments = space_catalyst_shadow.get("tickers_by_segment") or {}
        for segment, tickers in list(sorted(segments.items()))[:6]:
            lines.append(f"  {segment}: {', '.join(tickers)}")
        fields = space_catalyst_shadow.get("llm_event_fields") or []
        if fields:
            lines.append("  LLM fields: " + ", ".join(fields[:8]))
        forward = space_catalyst_shadow.get("forward_hypothesis") or {}
        if forward:
            extra_policies = []
            data_vendor_breakout_scalar = forward.get("data_vendor_breakout_risk_scalar")
            if data_vendor_breakout_scalar is not None:
                extra_policies.append(
                    f"data-vendor breakout @ {data_vendor_breakout_scalar}x"
                )
            launch_connectivity_trend_scalar = forward.get(
                "launch_connectivity_trend_risk_scalar"
            )
            if launch_connectivity_trend_scalar is not None:
                extra_policies.append(
                    "launch/connectivity trend @ "
                    f"{launch_connectivity_trend_scalar}x"
                )
            launch_connectivity_trend_target = forward.get(
                "launch_connectivity_trend_target_atr_mult"
            )
            if launch_connectivity_trend_target is not None:
                extra_policies.append(
                    "launch/connectivity trend target @ "
                    f"{launch_connectivity_trend_target} ATR"
                )
            official_trend_target = forward.get("official_trend_target_atr_mult")
            if official_trend_target is not None:
                extra_policies.append(
                    f"official trend target @ {official_trend_target} ATR"
                )
            basket_positive_scalar = forward.get("space_basket_positive_risk_scalar")
            if basket_positive_scalar is not None:
                extra_policies.append(
                    "Space basket positive 20d momentum @ "
                    f"{basket_positive_scalar}x"
                )
            perfect_tqs_scalar = forward.get("space_perfect_tqs_risk_scalar")
            if perfect_tqs_scalar is not None:
                extra_policies.append(
                    f"perfect Space TQS @ {perfect_tqs_scalar}x"
                )
            near_perfect_tqs_scalar = forward.get(
                "space_near_perfect_tqs_trend_risk_scalar"
            )
            if near_perfect_tqs_scalar is not None:
                extra_policies.append(
                    "near-perfect Space trend TQS @ "
                    f"{near_perfect_tqs_scalar}x"
                )
            peer_nonleader_breakout_scalar = forward.get(
                "space_peer_nonleader_breakout_risk_scalar"
            )
            if peer_nonleader_breakout_scalar is not None:
                extra_policies.append(
                    "peer-nonleader Space breakout @ "
                    f"{peer_nonleader_breakout_scalar}x"
                )
            iwm_relative_leader_scalar = forward.get(
                "space_iwm_relative_leader_risk_scalar"
            )
            if iwm_relative_leader_scalar is not None:
                extra_policies.append(
                    "IWM>SPY Space risk @ "
                    f"{iwm_relative_leader_scalar}x"
                )
            iwm_peer_leader_trend_scalar = forward.get(
                "space_iwm_peer_leader_trend_risk_scalar"
            )
            if iwm_peer_leader_trend_scalar is not None:
                extra_policies.append(
                    "IWM+peer-leader Space trend @ "
                    f"{iwm_peer_leader_trend_scalar}x"
                )
            launch_lunar_theme_scalar = forward.get(
                "space_launch_lunar_theme_risk_scalar"
            )
            if launch_lunar_theme_scalar is not None:
                extra_policies.append(
                    "launch/lunar theme risk @ "
                    f"{launch_lunar_theme_scalar}x"
                )
            liquidity_tier_scalar = forward.get(
                "space_liquidity_tier_risk_scalar"
            )
            liquidity_tier = forward.get("space_liquidity_tier")
            if liquidity_tier_scalar is not None:
                extra_policies.append(
                    f"liquidity tier {liquidity_tier} @ "
                    f"{liquidity_tier_scalar}x"
                )
            watch_liquidity_tier_scalar = forward.get(
                "space_watch_liquidity_tier_risk_scalar"
            )
            watch_liquidity_tier = forward.get("space_watch_liquidity_tier")
            if watch_liquidity_tier_scalar is not None:
                extra_policies.append(
                    f"liquidity tier {watch_liquidity_tier} @ "
                    f"{watch_liquidity_tier_scalar}x"
                )
            source_scalar = forward.get(
                "space_official_customer_source_risk_scalar"
            )
            source_field = forward.get(
                "space_official_customer_source_event_field"
            )
            if source_scalar is not None:
                extra_policies.append(
                    f"official customer source {source_field} @ "
                    f"{source_scalar}x"
                )
            source_peer_leader_scalar = forward.get(
                "space_customer_source_peer_leader_risk_scalar"
            )
            if source_peer_leader_scalar is not None:
                extra_policies.append(
                    "customer-source peer leader @ "
                    f"{source_peer_leader_scalar}x"
                )
            government_contract_peer_leader_scalar = forward.get(
                "space_government_contract_peer_leader_risk_scalar"
            )
            if government_contract_peer_leader_scalar is not None:
                extra_policies.append(
                    "government-contract peer leader @ "
                    f"{government_contract_peer_leader_scalar}x"
                )
            company_source_scalar = forward.get(
                "space_company_release_customer_source_risk_scalar"
            )
            if company_source_scalar is not None:
                extra_policies.append(
                    "company-release customer source @ "
                    f"{company_source_scalar}x"
                )
            profile_scalar = forward.get(
                "space_financing_dilution_profile_risk_scalar"
            )
            if profile_scalar is not None:
                extra_policies.append(
                    "financing/dilution profile @ "
                    f"{profile_scalar}x"
                )
            multi_event_scalar = forward.get(
                "space_multi_event_depth_risk_scalar"
            )
            multi_event_min_count = forward.get(
                "space_multi_event_depth_min_count"
            )
            if multi_event_scalar is not None:
                extra_policies.append(
                    "multi-event catalyst depth "
                    f">={multi_event_min_count} @ {multi_event_scalar}x"
                )
            single_event_defense_scalar = forward.get(
                "space_single_event_defense_risk_scalar"
            )
            if single_event_defense_scalar is not None:
                extra_policies.append(
                    "single-event defense-only @ "
                    f"{single_event_defense_scalar}x"
                )
            attention_overlay_scalar = forward.get(
                "space_attention_overlay_risk_scalar"
            )
            if attention_overlay_scalar is not None:
                extra_policies.append(
                    "attention overlay with official catalyst @ "
                    f"{attention_overlay_scalar}x"
                )
            source_diversity_scalar = forward.get(
                "space_source_diversity_risk_scalar"
            )
            if source_diversity_scalar is not None:
                extra_policies.append(
                    "official source diversity @ "
                    f"{source_diversity_scalar}x"
                )
            source_diversity_peer_leader_scalar = forward.get(
                "space_source_diversity_peer_leader_risk_scalar"
            )
            if source_diversity_peer_leader_scalar is not None:
                extra_policies.append(
                    "source-diversity peer leader @ "
                    f"{source_diversity_peer_leader_scalar}x"
                )
            source_diversity_iwm_leader_scalar = forward.get(
                "space_source_diversity_iwm_leader_risk_scalar"
            )
            if source_diversity_iwm_leader_scalar is not None:
                extra_policies.append(
                    "source-diversity IWM-leader @ "
                    f"{source_diversity_iwm_leader_scalar}x"
                )
            source_diversity_peer_iwm_leader_scalar = forward.get(
                "space_source_diversity_peer_iwm_leader_risk_scalar"
            )
            if source_diversity_peer_iwm_leader_scalar is not None:
                extra_policies.append(
                    "source-diversity peer+IWM leader @ "
                    f"{source_diversity_peer_iwm_leader_scalar}x"
                )
            forward_replacement_scalar = forward.get(
                "space_forward_replacement_positive_risk_scalar"
            )
            forward_replacement_horizon = forward.get(
                "space_forward_replacement_positive_horizon"
            )
            if forward_replacement_scalar is not None:
                extra_policies.append(
                    "forward replacement-positive "
                    f"{forward_replacement_horizon} @ {forward_replacement_scalar}x"
                )
            extra_policy = ""
            if extra_policies:
                extra_policy = "; " + "; ".join(extra_policies)
            lines.append(
                "  Forward hypothesis: "
                f"{forward.get('candidate_pool', 'n/a')} "
                f"@ {forward.get('risk_budget_scalar', 'n/a')}x risk "
                f"(default off{extra_policy})"
            )
        gates = space_catalyst_shadow.get("promotion_gates") or {}
        if gates:
            lines.append(
                "  Promotion gate: "
                f"{gates.get('minimum_closed_decisions', 'n/a')} closed decisions, "
                "positive direct and replacement value"
            )
    if space_catalyst_observation_slot and (
        space_catalyst_observation_slot.get("candidate_count", 0) > 0
        or space_catalyst_observation_slot.get("selected_count", 0) > 0
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SPACE CATALYST PRODUCTION OBSERVATION SLOT")
        lines.append("-" * 60)
        persistence = space_catalyst_observation_slot.get("persistence") or {}
        lines.append(
            f"  Mode: {space_catalyst_observation_slot.get('mode', 'production_observe_only')}  |  "
            f"Trade enabled: {space_catalyst_observation_slot.get('trade_enabled', False)}  |  "
            f"Live slots: {space_catalyst_observation_slot.get('live_slots', 0)}"
        )
        lines.append(
            f"  Candidates: {space_catalyst_observation_slot.get('candidate_count', 0)}  |  "
            f"Selected blocked plans: {space_catalyst_observation_slot.get('selected_count', 0)}"
        )
        if persistence:
            lines.append(
                f"  Ledger rows: {persistence.get('ledger_row_count', 0)}  |  "
                f"Appended today: {persistence.get('appended_count', 0)}"
            )
        for plan in (space_catalyst_observation_slot.get("blocked_trade_plans") or [])[:3]:
            target = plan.get("forward_target_price")
            target_text = f"${target:.2f}" if isinstance(target, (int, float)) else "n/a"
            entry = plan.get("entry_price")
            entry_text = f"${entry:.2f}" if isinstance(entry, (int, float)) else "n/a"
            risk_scalar = plan.get("effective_risk_scalar")
            risk_text = (
                f"{risk_scalar}x" if isinstance(risk_scalar, (int, float)) else "n/a"
            )
            basket_state = plan.get("space_basket_momentum_state")
            basket_text = f" basket={basket_state}" if basket_state else ""
            peer_state = plan.get("space_peer_momentum_state")
            peer_text = f" peer={peer_state}" if peer_state else ""
            iwm_state = plan.get("space_iwm_relative_state")
            iwm_text = f" iwm={iwm_state}" if iwm_state else ""
            theme_segment = plan.get("theme_segment")
            theme_text = f" theme={theme_segment}" if theme_segment else ""
            liquidity_tier = plan.get("liquidity_tier")
            liquidity_text = f" liquidity={liquidity_tier}" if liquidity_tier else ""
            watch_liquidity_text = (
                " watch_liquidity=True"
                if plan.get("space_watch_liquidity_tier_bucket")
                else ""
            )
            source_text = (
                " customer_source=True"
                if plan.get("space_official_customer_source_bucket")
                else ""
            )
            source_peer_leader_text = (
                " source_peer_leader=True"
                if plan.get("space_customer_source_peer_leader_bucket")
                else ""
            )
            government_contract_peer_leader_text = (
                " government_contract_peer_leader=True"
                if plan.get("space_government_contract_peer_leader_bucket")
                else ""
            )
            iwm_peer_leader_trend_text = (
                " iwm_peer_leader_trend=True"
                if plan.get("space_iwm_peer_leader_trend_bucket")
                else ""
            )
            company_source_text = (
                " company_release_source=True"
                if plan.get("space_company_release_customer_source_bucket")
                else ""
            )
            profile_text = (
                " financing_dilution_profile=True"
                if plan.get("space_financing_dilution_profile_bucket")
                else ""
            )
            multi_event_text = (
                " multi_event_depth=True"
                if plan.get("space_multi_event_depth_bucket")
                else ""
            )
            single_event_defense_text = (
                " single_event_defense=True"
                if plan.get("space_single_event_defense_bucket")
                else ""
            )
            attention_overlay_text = (
                " attention_overlay=True"
                if plan.get("space_attention_overlay_bucket")
                else ""
            )
            source_diversity_text = (
                " source_diversity=True"
                if plan.get("space_source_diversity_bucket")
                else ""
            )
            source_diversity_peer_leader_text = (
                " source_diversity_peer_leader=True"
                if plan.get("space_source_diversity_peer_leader_bucket")
                else ""
            )
            source_diversity_iwm_leader_text = (
                " source_diversity_iwm_leader=True"
                if plan.get("space_source_diversity_iwm_leader_bucket")
                else ""
            )
            source_diversity_peer_iwm_leader_text = (
                " source_diversity_peer_iwm_leader=True"
                if plan.get("space_source_diversity_peer_iwm_leader_bucket")
                else ""
            )
            forward_replacement_text = (
                " forward_replacement_positive=True"
                if plan.get("space_forward_replacement_positive_bucket")
                else ""
            )
            perfect_tqs_text = (
                " perfect_tqs=True" if plan.get("space_perfect_tqs_bucket") else ""
            )
            near_perfect_tqs_text = (
                " near_perfect_tqs_trend=True"
                if plan.get("space_near_perfect_tqs_trend_bucket")
                else ""
            )
            peer_nonleader_breakout_text = (
                " peer_nonleader_breakout=True"
                if plan.get("space_peer_nonleader_breakout_bucket")
                else ""
            )
            lines.append(
                f"  {plan.get('ticker', '?')}: {plan.get('strategy', '?')} "
                f"entry {entry_text} target {target_text} "
                f"TQS={plan.get('trade_quality_score', 'n/a')} "
                f"risk={risk_text}{basket_text}{peer_text}{iwm_text}{theme_text}"
                f"{liquidity_text}{watch_liquidity_text}{source_text}"
                f"{source_peer_leader_text}{government_contract_peer_leader_text}"
                f"{iwm_peer_leader_trend_text}"
                f"{company_source_text}{profile_text}"
                f"{multi_event_text}{single_event_defense_text}"
                f"{attention_overlay_text}{source_diversity_text}"
                f"{source_diversity_peer_leader_text}"
                f"{source_diversity_iwm_leader_text}"
                f"{source_diversity_peer_iwm_leader_text}"
                f"{forward_replacement_text}"
                f"{perfect_tqs_text}"
                f"{near_perfect_tqs_text}{peer_nonleader_breakout_text} "
                f"({plan.get('blocked_reason', 'observe_only')})"
            )
    if space_catalyst_event_ledger and (
        space_catalyst_event_ledger.get("active_event_count", 0) > 0
        or space_catalyst_event_ledger.get("event_row_count", 0) > 0
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SPACE CATALYST EVENT LEDGER")
        lines.append("-" * 60)
        persistence = space_catalyst_event_ledger.get("persistence") or {}
        gate = space_catalyst_event_ledger.get("promotion_gate") or {}
        lines.append(
            f"  Mode: {space_catalyst_event_ledger.get('mode', 'observe_only')}  |  "
            f"Events: {space_catalyst_event_ledger.get('active_event_count', 0)}  |  "
            f"Rows: {space_catalyst_event_ledger.get('event_row_count', 0)}  |  "
            f"Closed 10d: {space_catalyst_event_ledger.get('closed_decision_count', 0)}"
        )
        if persistence:
            lines.append(
                f"  Ledger rows: {persistence.get('ledger_row_count', 0)}  |  "
                f"Appended today: {persistence.get('appended_count', 0)}"
            )
        lines.append(
            f"  Promotion gate: {'PASS' if gate.get('passed') else 'BLOCKED'} "
            f"({gate.get('reason', 'observe_only')})"
        )
        by_bucket = (
            (space_catalyst_event_ledger.get("aggregate") or {})
            .get("by_semantic_bucket_count")
            or {}
        )
        if by_bucket:
            bucket_text = ", ".join(
                f"{bucket}={count}" for bucket, count in sorted(by_bucket.items())
            )
            lines.append(f"  Buckets: {bucket_text}")
        for row in (space_catalyst_event_ledger.get("event_rows") or [])[:6]:
            h10 = (row.get("horizons") or {}).get("10d") or {}
            ret = h10.get("event_return")
            ret_text = (
                f"{ret * 100:.2f}%"
                if isinstance(ret, (int, float))
                else h10.get("status", "pending")
            )
            lines.append(
                f"  {row.get('ticker', '?')}: {row.get('semantic_bucket', 'unknown')} "
                f"{row.get('event_date')} 10d={ret_text} "
                f"closed={row.get('closed_decision', False)}"
            )

    addon_actions = addon_actions or []
    if addon_actions:
        lines.append("\n" + "-" * 60)
        lines.append("FOLLOW-THROUGH ADD-ONS")
        lines.append("-" * 60)
        for action in addon_actions:
            lines.append(
                f"\n{action.get('ticker', '?')}: ADD "
                f"{action.get('shares_to_buy', '?')} shares "
                f"at next session open"
            )
            lines.append(
                f"   Checkpoint: day {action.get('checkpoint_days')}  |  "
                f"Unrealized: {action.get('unrealized_pct', 0)*100:.1f}%  |  "
                f"RS vs SPY: {action.get('rs_vs_spy', 0)*100:.1f}%"
            )
            lines.append(f"   Reason:     {action.get('reason', '')}")

    if pilot_attribution:
        lines.append("\n" + "-" * 60)
        lines.append("PILOT SLEEVE ATTRIBUTION")
        lines.append("-" * 60)
        lines.append(
            f"  Decision snapshots: {pilot_attribution.get('decision_snapshots', 0)}"
        )
        lines.append(
            f"  Outcome records:    {pilot_attribution.get('outcome_records', 0)}"
        )
        if pilot_attribution.get("outcome_records", 0) > 0:
            direct_pnl = pilot_attribution.get("direct_pilot_pnl", 0.0)
            cash_pnl = pilot_attribution.get("cash_relative_pnl", 0.0)
            repl_value = pilot_attribution.get("replacement_value")
            repl_text = (
                f"${repl_value:,.2f}"
                if isinstance(repl_value, (int, float))
                else "pending"
            )
            lines.append(f"  Direct pilot P&L:  ${direct_pnl:,.2f}")
            lines.append(f"  Cash-relative P&L: ${cash_pnl:,.2f}")
            lines.append(f"  Replacement value: {repl_text}")
            lines.append(
                "  Replacement outcomes: "
                f"{pilot_attribution.get('complete_replacement_outcomes', 0)} complete, "
                f"{pilot_attribution.get('pending_replacement_outcomes', 0)} pending"
            )
            rav = pilot_attribution.get("risk_adjusted_replacement_value_avg")
            if rav is not None:
                lines.append(f"  Avg risk-adjusted replacement value: {rav}")
        else:
            lines.append("  No closed pilot outcomes logged yet.")

    if ai_infra_aggressive_attribution:
        lines.append("\n" + "-" * 60)
        lines.append("AI INFRA AGGRESSIVE SLEEVE")
        lines.append("-" * 60)
        lines.append(
            "  Bull booster: "
            f"{ai_infra_aggressive_attribution.get('bull_booster_active', False)}  |  "
            "Max slots: "
            f"{ai_infra_aggressive_attribution.get('max_concurrent_positions', 'n/a')}"
        )
        selected = ai_infra_aggressive_attribution.get("selected") or []
        sliced = ai_infra_aggressive_attribution.get("sliced") or []
        lines.append(f"  Selected: {len(selected)}  |  Sliced: {len(sliced)}")
        for item in selected[:5]:
            lines.append(
                "  "
                f"{item.get('ticker', '?')} "
                f"({item.get('segment', 'unknown')}): "
                f"TQS={item.get('trade_quality_score', 'n/a')} "
                f"shares={item.get('shares_to_buy', 'n/a')}"
            )
        repl_value = ai_infra_aggressive_attribution.get("core_replacement_value")
        if isinstance(repl_value, (int, float)):
            lines.append(f"  Core replacement value: ${repl_value:,.2f}")
        else:
            lines.append("  Core replacement value: pending")

    if form4_event_queue and (
        form4_event_queue.get("candidate_count", 0) > 0
        or form4_event_queue.get("data_source", {}).get("status") != "loaded"
    ):
        lines.append("\n" + "-" * 60)
        lines.append("FORM 4 FORWARD EVENT QUEUE")
        lines.append("-" * 60)
        lines.append(
            f"  Enabled: {form4_event_queue.get('enabled', False)}  |  "
            f"Candidates: {form4_event_queue.get('candidate_count', 0)}"
        )
        source = form4_event_queue.get("data_source") or {}
        if source.get("status") != "loaded":
            lines.append(f"  Source status: {source.get('status')}")
        for candidate in (form4_event_queue.get("candidates") or [])[:5]:
            total_purchase = candidate.get("total_purchase_value") or 0
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"${total_purchase:,.0f} insider buy "
                f"on {candidate.get('usable_trade_date', '?')} "
                "(observe only)"
            )

    # ── Trade candidates ────────────────────────────────────────────────────
    if form4_event_sleeve and (
        form4_event_sleeve.get("pending_count", 0) > 0
        or form4_event_sleeve.get("open_position_count", 0) > 0
        or form4_event_sleeve.get("closed_count_today", 0) > 0
        or form4_event_sleeve.get("error")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("FORM 4 PAPER EVENT SLEEVE")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {form4_event_sleeve.get('paper_enabled', False)}  |  "
            f"Trade enabled: {form4_event_sleeve.get('trade_enabled', False)}"
        )
        if form4_event_sleeve.get("error"):
            lines.append(f"  Source status: {form4_event_sleeve.get('error')}")
        lines.append(
            f"  Pending: {form4_event_sleeve.get('pending_count', 0)}  |  "
            f"Open: {form4_event_sleeve.get('open_position_count', 0)}  |  "
            f"Closed today: {form4_event_sleeve.get('closed_count_today', 0)}"
        )
        lines.append(
            "  Realized paper P&L: "
            f"${form4_event_sleeve.get('realized_pnl_to_date', 0.0):,.2f}  |  "
            f"Unrealized: ${form4_event_sleeve.get('unrealized_pnl', 0.0):,.2f}"
        )
        for position in (form4_event_sleeve.get("open_positions") or [])[:5]:
            lines.append(
                f"  {position.get('ticker', '?')}: paper open "
                f"since {position.get('entry_date', '?')} "
                f"({position.get('observed_trading_days', 0)}/"
                f"{position.get('hold_days', '?')} days)"
            )

    if sec_event_queue and (
        sec_event_queue.get("candidate_count", 0) > 0
        or sec_event_queue.get("data_source", {}).get("status") != "loaded"
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC NEGATIVE-REACTION EVENT QUEUE")
        lines.append("-" * 60)
        lines.append(
            f"  Enabled: {sec_event_queue.get('enabled', False)}  |  "
            f"Candidates: {sec_event_queue.get('candidate_count', 0)}"
        )
        source = sec_event_queue.get("data_source") or {}
        if source.get("status") != "loaded":
            lines.append(f"  Source status: {source.get('status')}")
        for candidate in (sec_event_queue.get("candidates") or [])[:5]:
            excess = candidate.get("reaction_excess_return")
            excess_text = f"{excess * 100:.2f}%" if isinstance(excess, (int, float)) else "n/a"
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"{candidate.get('language_bucket', 'negative_language')} / "
                f"reaction excess {excess_text} "
                f"on {candidate.get('reaction_date', candidate.get('usable_trade_date', '?'))} "
                "(observe only)"
            )

    if sec_negative_event_sleeve and (
        sec_negative_event_sleeve.get("pending_count", 0) > 0
        or sec_negative_event_sleeve.get("open_position_count", 0) > 0
        or sec_negative_event_sleeve.get("closed_count_today", 0) > 0
        or sec_negative_event_sleeve.get("error")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC NEGATIVE-REACTION PAPER EVENT SLEEVE")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {sec_negative_event_sleeve.get('paper_enabled', False)}  |  "
            f"Trade enabled: {sec_negative_event_sleeve.get('trade_enabled', False)}"
        )
        if sec_negative_event_sleeve.get("error"):
            lines.append(f"  Source status: {sec_negative_event_sleeve.get('error')}")
        lines.append(
            f"  Pending: {sec_negative_event_sleeve.get('pending_count', 0)}  |  "
            f"Open: {sec_negative_event_sleeve.get('open_position_count', 0)}  |  "
            f"Closed today: {sec_negative_event_sleeve.get('closed_count_today', 0)}"
        )
        lines.append(
            "  Realized paper P&L: "
            f"${sec_negative_event_sleeve.get('realized_pnl_to_date', 0.0):,.2f}  |  "
            f"Unrealized: ${sec_negative_event_sleeve.get('unrealized_pnl', 0.0):,.2f}"
        )
        for position in (sec_negative_event_sleeve.get("open_positions") or [])[:5]:
            lines.append(
                f"  {position.get('ticker', '?')}: paper open "
                f"since {position.get('entry_date', '?')} "
                f"({position.get('observed_trading_days', 0)}/"
                f"{position.get('hold_days', '?')} days)"
            )

    if sec_governance_event_queue and (
        sec_governance_event_queue.get("candidate_count", 0) > 0
        or sec_governance_event_queue.get("data_source", {}).get("status") != "loaded"
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC GOVERNANCE/PROCEDURAL EVENT QUEUE")
        lines.append("-" * 60)
        lines.append(
            f"  Enabled: {sec_governance_event_queue.get('enabled', False)}  |  "
            f"Candidates: {sec_governance_event_queue.get('candidate_count', 0)}"
        )
        source = sec_governance_event_queue.get("data_source") or {}
        if source.get("status") != "loaded":
            lines.append(f"  Source status: {source.get('status')}")
        for candidate in (sec_governance_event_queue.get("candidates") or [])[:5]:
            excess = candidate.get("reaction_excess_return")
            excess_text = f"{excess * 100:.2f}%" if isinstance(excess, (int, float)) else "n/a"
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"{candidate.get('target_cell', 'governance/procedural')} / "
                f"reaction excess {excess_text} "
                f"on {candidate.get('reaction_date', candidate.get('usable_trade_date', '?'))} "
                "(paper only)"
            )

    if sec_governance_event_sleeve and (
        sec_governance_event_sleeve.get("pending_count", 0) > 0
        or sec_governance_event_sleeve.get("open_position_count", 0) > 0
        or sec_governance_event_sleeve.get("closed_count_today", 0) > 0
        or sec_governance_event_sleeve.get("error")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC GOVERNANCE PAPER EVENT SLEEVE")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {sec_governance_event_sleeve.get('paper_enabled', False)}  |  "
            f"Trade enabled: {sec_governance_event_sleeve.get('trade_enabled', False)}"
        )
        if sec_governance_event_sleeve.get("error"):
            lines.append(f"  Source status: {sec_governance_event_sleeve.get('error')}")
        lines.append(
            f"  Pending: {sec_governance_event_sleeve.get('pending_count', 0)}  |  "
            f"Open: {sec_governance_event_sleeve.get('open_position_count', 0)}  |  "
            f"Closed today: {sec_governance_event_sleeve.get('closed_count_today', 0)}"
        )
        lines.append(
            "  Realized paper P&L: "
            f"${sec_governance_event_sleeve.get('realized_pnl_to_date', 0.0):,.2f}  |  "
            f"Unrealized: ${sec_governance_event_sleeve.get('unrealized_pnl', 0.0):,.2f}"
        )
        for position in (sec_governance_event_sleeve.get("open_positions") or [])[:5]:
            lines.append(
                f"  {position.get('ticker', '?')}: paper open "
                f"since {position.get('entry_date', '?')} "
                f"({position.get('observed_trading_days', 0)}/"
                f"{position.get('hold_days', '?')} days)"
            )

    if sec_leadership_event_queue and (
        sec_leadership_event_queue.get("candidate_count", 0) > 0
        or sec_leadership_event_queue.get("data_source", {}).get("status") != "loaded"
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC LEADERSHIP-CHANGE EVENT QUEUE")
        lines.append("-" * 60)
        lines.append(
            f"  Enabled: {sec_leadership_event_queue.get('enabled', False)}  |  "
            f"Candidates: {sec_leadership_event_queue.get('candidate_count', 0)}"
        )
        source = sec_leadership_event_queue.get("data_source") or {}
        if source.get("status") != "loaded":
            lines.append(f"  Source status: {source.get('status')}")
        for candidate in (sec_leadership_event_queue.get("candidates") or [])[:5]:
            excess = candidate.get("reaction_excess_return")
            excess_text = f"{excess * 100:.2f}%" if isinstance(excess, (int, float)) else "n/a"
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"{candidate.get('target_cell', 'leadership_change')} / "
                f"reaction excess {excess_text} "
                f"on {candidate.get('reaction_date', candidate.get('usable_trade_date', '?'))} "
                "(paper only)"
            )

    if sec_leadership_event_sleeve and (
        sec_leadership_event_sleeve.get("pending_count", 0) > 0
        or sec_leadership_event_sleeve.get("open_position_count", 0) > 0
        or sec_leadership_event_sleeve.get("closed_count_today", 0) > 0
        or sec_leadership_event_sleeve.get("error")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC LEADERSHIP PAPER EVENT SLEEVE")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {sec_leadership_event_sleeve.get('paper_enabled', False)}  |  "
            f"Trade enabled: {sec_leadership_event_sleeve.get('trade_enabled', False)}"
        )
        if sec_leadership_event_sleeve.get("error"):
            lines.append(f"  Source status: {sec_leadership_event_sleeve.get('error')}")
        lines.append(
            f"  Pending: {sec_leadership_event_sleeve.get('pending_count', 0)}  |  "
            f"Open: {sec_leadership_event_sleeve.get('open_position_count', 0)}  |  "
            f"Closed today: {sec_leadership_event_sleeve.get('closed_count_today', 0)}"
        )
        lines.append(
            "  Realized paper P&L: "
            f"${sec_leadership_event_sleeve.get('realized_pnl_to_date', 0.0):,.2f}  |  "
            f"Unrealized: ${sec_leadership_event_sleeve.get('unrealized_pnl', 0.0):,.2f}"
        )
        for position in (sec_leadership_event_sleeve.get("open_positions") or [])[:5]:
            lines.append(
                f"  {position.get('ticker', '?')}: paper open "
                f"since {position.get('entry_date', '?')} "
                f"({position.get('observed_trading_days', 0)}/"
                f"{position.get('hold_days', '?')} days)"
            )

    if sec_financial_report_t1_queue and (
        sec_financial_report_t1_queue.get("candidate_count", 0) > 0
        or sec_financial_report_t1_queue.get("data_source", {}).get("status") != "loaded"
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC FINANCIAL-REPORT T+1 DRIFT QUEUE")
        lines.append("-" * 60)
        lines.append(
            f"  Enabled: {sec_financial_report_t1_queue.get('enabled', False)}  |  "
            f"Candidates: {sec_financial_report_t1_queue.get('candidate_count', 0)}"
        )
        source = sec_financial_report_t1_queue.get("data_source") or {}
        if source.get("status") != "loaded":
            lines.append(f"  Source status: {source.get('status')}")
        for candidate in (sec_financial_report_t1_queue.get("candidates") or [])[:5]:
            excess = candidate.get("t1_excess_return_vs_spy")
            excess_text = f"{excess * 100:.2f}%" if isinstance(excess, (int, float)) else "n/a"
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"{candidate.get('event_family', 'financial_report')} / "
                f"T+1 excess {excess_text} "
                f"on {candidate.get('t1_date', candidate.get('usable_trade_date', '?'))} "
                "(paper only)"
            )

    if sec_financial_report_event_sleeve and (
        sec_financial_report_event_sleeve.get("pending_count", 0) > 0
        or sec_financial_report_event_sleeve.get("open_position_count", 0) > 0
        or sec_financial_report_event_sleeve.get("closed_count_today", 0) > 0
        or sec_financial_report_event_sleeve.get("error")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("SEC FINANCIAL-REPORT PAPER EVENT SLEEVE")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {sec_financial_report_event_sleeve.get('paper_enabled', False)}  |  "
            f"Trade enabled: {sec_financial_report_event_sleeve.get('trade_enabled', False)}"
        )
        if sec_financial_report_event_sleeve.get("error"):
            lines.append(f"  Source status: {sec_financial_report_event_sleeve.get('error')}")
        lines.append(
            f"  Pending: {sec_financial_report_event_sleeve.get('pending_count', 0)}  |  "
            f"Open: {sec_financial_report_event_sleeve.get('open_position_count', 0)}  |  "
            f"Closed today: {sec_financial_report_event_sleeve.get('closed_count_today', 0)}"
        )
        lines.append(
            "  Realized paper P&L: "
            f"${sec_financial_report_event_sleeve.get('realized_pnl_to_date', 0.0):,.2f}  |  "
            f"Unrealized: ${sec_financial_report_event_sleeve.get('unrealized_pnl', 0.0):,.2f}"
        )
        for position in (sec_financial_report_event_sleeve.get("open_positions") or [])[:5]:
            lines.append(
                f"  {position.get('ticker', '?')}: paper open "
                f"since {position.get('entry_date', '?')} "
                f"({position.get('observed_trading_days', 0)}/"
                f"{position.get('hold_days', '?')} days)"
            )

    if event_sleeve_bundle and (
        event_sleeve_bundle.get("pending_count", 0) > 0
        or event_sleeve_bundle.get("open_position_count", 0) > 0
        or event_sleeve_bundle.get("closed_count_today", 0) > 0
        or event_sleeve_bundle.get("error")
        or event_sleeve_bundle.get("source_summaries")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("DEFAULT-OFF EVENT OVERLAY BUNDLE")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {event_sleeve_bundle.get('paper_enabled', False)}  |  "
            f"Trade enabled: {event_sleeve_bundle.get('trade_enabled', False)}"
        )
        if event_sleeve_bundle.get("error"):
            lines.append(f"  Source status: {event_sleeve_bundle.get('error')}")
        lines.append(
            f"  Pending: {event_sleeve_bundle.get('pending_count', 0)}  |  "
            f"Open: {event_sleeve_bundle.get('open_position_count', 0)}  |  "
            f"Closed today: {event_sleeve_bundle.get('closed_count_today', 0)}"
        )
        if event_sleeve_bundle.get("raw_candidate_count") is not None:
            lines.append(
                f"  Candidates: raw={event_sleeve_bundle.get('raw_candidate_count', 0)} "
                f"deduped={event_sleeve_bundle.get('deduped_candidate_count', 0)} "
                f"duplicates={event_sleeve_bundle.get('duplicate_candidate_count', 0)}"
            )
        lines.append(
            "  Realized paper P&L: "
            f"${event_sleeve_bundle.get('realized_pnl_to_date', 0.0):,.2f}  |  "
            f"Unrealized: ${event_sleeve_bundle.get('unrealized_pnl', 0.0):,.2f}"
        )
        state_surface_addon = event_sleeve_bundle.get("state_surface_addon") or {}
        if state_surface_addon:
            eligible_surfaces = state_surface_addon.get("eligible_surfaces") or []
            surface_text = ", ".join(str(surface) for surface in eligible_surfaces)
            if not surface_text:
                surface_text = "none"
            lines.append(
                "  State-surface add-on: "
                f"eligible={state_surface_addon.get('eligible_candidate_count', 0)}/"
                f"{state_surface_addon.get('candidate_count', 0)} "
                f"incremental=${state_surface_addon.get('incremental_notional_usd', 0.0):,.2f} "
                f"rotation={state_surface_addon.get('rotation_tilt_candidate_count', 0)} "
                f"surfaces={surface_text}"
            )
        gate = event_sleeve_bundle.get("forward_paper_gate") or {}
        if gate:
            gate_metrics = gate.get("metrics") or {}
            reasons = gate.get("reasons") or []
            reason_text = ", ".join(reasons) if reasons else "none"
            lines.append(
                f"  Forward gate: {gate.get('status', 'unknown')}  |  "
                f"closed={gate_metrics.get('closed_trades', 0)} "
                f"WR={gate_metrics.get('win_rate')} "
                f"DD={gate_metrics.get('max_drawdown_pct')}  |  "
                f"blocked_by={reason_text}"
            )
        kill = event_sleeve_bundle.get("kill_switch") or {}
        if kill:
            reasons = kill.get("reasons") or []
            reason_text = ", ".join(reasons) if reasons else "none"
            lines.append(
                f"  Kill switch: {kill.get('status', 'unknown')}  |  "
                f"reasons={reason_text}"
            )
        summaries = event_sleeve_bundle.get("source_summaries") or {}
        for source in (
            "form4_meaningful_purchase",
            "sec_negative_reaction",
            "sec_governance_procedural",
        ):
            summary = summaries.get(source)
            if not summary:
                continue
            lines.append(
                f"  {summary.get('label', source)}: "
                f"pending={summary.get('pending_count', 0)} "
                f"open={summary.get('open_position_count', 0)} "
                f"closed_today={summary.get('closed_count_today', 0)} "
                f"realized=${summary.get('realized_pnl_to_date', 0.0):,.2f}"
            )

    if state_surface_sleeve and (
        state_surface_sleeve.get("candidate_count", 0) > 0
        or state_surface_sleeve.get("pending_count", 0) > 0
        or state_surface_sleeve.get("open_position_count", 0) > 0
        or state_surface_sleeve.get("closed_count_today", 0) > 0
        or state_surface_sleeve.get("error")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("STATE-SURFACE SATELLITE PAPER SLEEVE")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {state_surface_sleeve.get('paper_enabled', False)}  |  "
            f"Trade enabled: {state_surface_sleeve.get('trade_enabled', False)}"
        )
        if state_surface_sleeve.get("error"):
            lines.append(f"  Source status: {state_surface_sleeve.get('error')}")
        lines.append(
            f"  Candidates: {state_surface_sleeve.get('candidate_count', 0)}  |  "
            f"Pending: {state_surface_sleeve.get('pending_count', 0)}  |  "
            f"Open: {state_surface_sleeve.get('open_position_count', 0)}  |  "
            f"Closed today: {state_surface_sleeve.get('closed_count_today', 0)}"
        )
        lines.append(
            "  Realized paper P&L: "
            f"${state_surface_sleeve.get('realized_pnl_to_date', 0.0):,.2f}  |  "
            f"Unrealized: ${state_surface_sleeve.get('unrealized_pnl', 0.0):,.2f}"
        )
        gate = state_surface_sleeve.get("forward_paper_gate") or {}
        if gate:
            metrics = gate.get("metrics") or {}
            reasons = gate.get("reasons") or []
            reason_text = ", ".join(reasons) if reasons else "none"
            lines.append(
                f"  Forward gate: {gate.get('status', 'unknown')}  |  "
                f"closed={metrics.get('closed_trades', 0)} "
                f"WR={metrics.get('win_rate')}  |  blocked_by={reason_text}"
            )
        state = state_surface_sleeve.get("state") or {}
        if state:
            lines.append(
                "  State: "
                f"{state.get('state_bucket', 'unknown')} / "
                f"{state.get('breadth_bucket', 'unknown')} / "
                f"{state.get('dispersion_bucket', 'unknown')}"
            )
        for candidate in (state_surface_sleeve.get("candidates") or [])[:5]:
            score = candidate.get("score")
            score_text = f"{score:.3f}" if isinstance(score, (int, float)) else "n/a"
            lines.append(
                f"  {candidate.get('ticker', '?')}: "
                f"{candidate.get('surface', 'surface')} "
                f"rank={candidate.get('rank', '?')} score={score_text} "
                "(paper only)"
            )

    if low_deployment_etf_overlay and (
        low_deployment_etf_overlay.get("candidate_count", 0) > 0
        or low_deployment_etf_overlay.get("closed_count_today", 0) > 0
        or low_deployment_etf_overlay.get("closed_position_count", 0) > 0
        or low_deployment_etf_overlay.get("error")
    ):
        lines.append("\n" + "-" * 60)
        lines.append("LOW-DEPLOYMENT ETF OVERLAY PAPER")
        lines.append("-" * 60)
        lines.append(
            f"  Paper: {low_deployment_etf_overlay.get('paper_enabled', False)}  |  "
            f"Trade enabled: {low_deployment_etf_overlay.get('trade_enabled', False)}"
        )
        if low_deployment_etf_overlay.get("error"):
            lines.append(f"  Source status: {low_deployment_etf_overlay.get('error')}")
        lines.append(
            f"  Active core positions: {low_deployment_etf_overlay.get('active_core_positions')}  |  "
            f"Closed today: {low_deployment_etf_overlay.get('closed_count_today', 0)}  |  "
            f"Closed total: {low_deployment_etf_overlay.get('closed_position_count', 0)}"
        )
        lines.append(
            "  Realized paper P&L: "
            f"${low_deployment_etf_overlay.get('realized_pnl_to_date', 0.0):,.2f}"
        )
        gate = low_deployment_etf_overlay.get("forward_paper_gate") or {}
        if gate:
            metrics = gate.get("metrics") or {}
            reasons = gate.get("reasons") or []
            reason_text = ", ".join(reasons) if reasons else "none"
            lines.append(
                f"  Forward gate: {gate.get('status', 'unknown')}  |  "
                f"closed={metrics.get('closed_trades', 0)} "
                f"WR={metrics.get('win_rate')}  |  blocked_by={reason_text}"
            )
        candidate = low_deployment_etf_overlay.get("candidate") or {}
        if candidate:
            lines.append(
                f"  Candidate: {candidate.get('ticker', '?')} "
                f"mom20={candidate.get('prior_momentum20')} "
                f"decision={candidate.get('decision_date')} "
                f"trade_date={candidate.get('trade_date')} (paper only)"
            )

    lines.append("\n" + "-" * 60)
    lines.append("TOP TRADE CANDIDATES")
    lines.append("-" * 60)

    if dropped_signals:
        lines.append(f"\n  ⚠ {len(dropped_signals)} signal(s) dropped during enrichment:")
        for d in dropped_signals:
            lines.append(f"    {d['ticker']:6s}  {d.get('strategy','?'):22s}  → {d['reason']}")

    if not signals:
        lines.append("  No signals generated today.")
    else:
        for i, sig in enumerate(signals[:10], 1):
            ticker  = sig["ticker"]
            strat   = sig["strategy"]
            entry   = sig.get("entry_price", "?")
            stop    = sig.get("stop_price",  "?")
            target  = sig.get("target_price", "?")
            conf    = sig.get("confidence_score", "?")
            rr      = sig.get("risk_reward_ratio")
            dte     = sig.get("days_to_earnings")
            sizing  = sig.get("sizing", {})
            shares  = sizing.get("shares_to_buy",    "?")
            pos_val = sizing.get("position_value_usd")

            lines.append(f"\n{i}. {ticker}")
            lines.append(f"   Strategy:    {strat}")
            lines.append(f"   Entry:       ${entry}")
            lines.append(f"   Stop:        ${stop}  |  Target: ${target}")
            if rr is not None:
                lines.append(f"   R:R:         {rr}:1")
            lines.append(f"   Confidence:  {conf}")

            if shares != "?":
                val_str = f"  (${pos_val:,.0f})" if pos_val else ""
                lines.append(f"   Sizing:      {shares} shares{val_str}")

            if dte is not None:
                lines.append(f"   Earnings in: {dte} days")

            conds = sig.get("conditions_met", {})
            if conds:
                parts = [f"{k}={v}" for k, v in conds.items() if v is not None]
                lines.append(f"   Conditions:  {', '.join(parts)}")

    # ── Positions requiring attention (20d breakdown) ───────────────────────
    attention = []
    if features_dict:
        for ticker, feats in features_dict.items():
            if feats and feats.get("breakdown_20d"):
                close   = feats.get("close", "?")
                low_20d = feats.get("low_20d", "?")
                attention.append(
                    f"  {ticker}: 20d breakdown  close={close}  20d_low={low_20d}"
                )

    if attention:
        lines.append("\n" + "-" * 60)
        lines.append("POSITIONS REQUIRING ATTENTION  (20-day breakdown)")
        lines.append("-" * 60)
        for a in attention:
            lines.append(a)

    # ── Performance metrics ─────────────────────────────────────────────────
    if metrics and metrics.get("total_trades", 0) > 0:
        lines.append("\n" + "-" * 60)
        lines.append("PERFORMANCE METRICS  (realized P&L)")
        lines.append("-" * 60)
        lines.append(f"  Closed trades:   {metrics['total_trades']}")
        lines.append(f"  Open trades:     {metrics.get('open_trades', 0)}")
        lines.append(f"  Win rate:        {metrics['win_rate']*100:.1f}%")
        lines.append(f"  Avg win:         ${metrics['avg_win_usd']:,.2f}")
        lines.append(f"  Avg loss:        ${metrics['avg_loss_usd']:,.2f}")
        lines.append(f"  Expected value:  ${metrics['expected_value_usd']:,.2f} per trade")
        lines.append(f"  Max drawdown:    ${metrics['max_drawdown_usd']:,.2f}")
        lines.append(f"  Total P&L:       ${metrics['total_pnl_usd']:,.2f}")

        by_strat = metrics.get("by_strategy", {})
        if by_strat:
            lines.append("\n  By strategy:")
            for strat, s in by_strat.items():
                lines.append(
                    f"    {strat}: {s['trades']} trades  "
                    f"WR={s['win_rate']*100:.0f}%  "
                    f"P&L=${s['total_pnl']:,.2f}"
                )

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def save_report(report_text, filepath=None):
    """
    Save the report to a dated text file.

    Default path: data/report_YYYYMMDD.txt

    Returns:
        str: Saved file path, or None on error
    """
    if filepath is None:
        today    = datetime.now().strftime("%Y%m%d")
        filepath = os.path.join(
            os.path.dirname(__file__), '..', 'data', f'report_{today}.txt'
        )

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"Report saved to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        return None
