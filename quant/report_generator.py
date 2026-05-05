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
                           form4_event_queue=None,
                           form4_event_sleeve=None,
                           sec_event_queue=None,
                           sec_negative_event_sleeve=None,
                           sec_governance_event_queue=None,
                           sec_governance_event_sleeve=None,
                           event_sleeve_bundle=None,
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
        form4_event_queue (dict):       Default-off Form 4 observation queue
        form4_event_sleeve (dict):      Default-off Form 4 paper event sleeve
        sec_event_queue (dict):         Default-off SEC negative-reaction queue
        sec_negative_event_sleeve (dict): Default-off SEC negative-reaction paper sleeve
        sec_governance_event_queue (dict): Default-off SEC governance/procedural queue
        sec_governance_event_sleeve (dict): Default-off SEC governance paper sleeve
        event_sleeve_bundle (dict):     Default-off aggregate event overlay attribution
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
