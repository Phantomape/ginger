"""
Unified Quant Pipeline — single daily entry point.

Replaces both run_quant.py (technical signals) and run_pipeline.py (news + LLM).

Steps:
  1.  Load config (open_positions, universe)
  2.  Market regime           — SPY/QQQ vs 200-day MA        (single call)
  3.  OHLCV + earnings data   — 350 calendar days per ticker  (single download)
  4.  Feature layer           — trend score, breakout, ATR, earnings features
  5.  Position context        — exit levels / exit signals for held tickers
  6.  Quant signals           — 3 strategies, risk enrichment, position sizing
  7.  Quant report            — daily report + quant_signals_YYYYMMDD.json
  8.  Fetch & filter news     — RSS sources → hygiene → trade filter
  9.  LLM prompt              — save prompt to data/llm_prompt_YYYYMMDD.txt
  10. Summary

Usage:
    cd d:/Github/ginger
    python quant/run.py
"""

import json
import logging
import os
from datetime import datetime

import pandas as pd

from constants import (
    ENABLED_STRATEGIES,
    ATR_TARGET_MULT,
    BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
    BREAKOUT_RANK_BY_52W_HIGH,
    REGIME_AWARE_EXIT,
)
from earnings_snapshot import persist_earnings_snapshot
from regime_exit import compute_regime_exit_profile


# ── Logging ──────────────────────────────────────────────────────────────────
# colorlog adds ANSI colours: DEBUG=cyan, INFO=green, WARNING=yellow,
# ERROR=red, CRITICAL=bold red.  Falls back to plain logging if unavailable.

try:
    import colorlog
    _handler = colorlog.StreamHandler()
    _handler.setFormatter(colorlog.ColoredFormatter(
        fmt="%(asctime)s  %(log_color)s%(levelname)-7s%(reset)s  %(cyan)s%(name)s%(reset)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "bold_red",
        },
    ))
    logging.root.setLevel(logging.INFO)
    logging.root.handlers = [_handler]
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _save_json(obj, filepath):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)
    log.info(f"Saved → {filepath}")


def _save_text(text, filepath):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    log.info(f"Saved → {filepath}")


def _load_open_positions():
    for path in [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'open_positions.json'),
        'data/open_positions.json',
    ]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    log.warning("open_positions.json not found")
    return None


def _print_section(title):
    log.info("")
    log.info("=" * 55)
    log.info(f"  {title}")
    log.info("=" * 55)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y%m%d")

    # ── Step 1: Config ────────────────────────────────────────────────────────
    _print_section("STEP 1 — Loading config")

    # Imports are inside main() so the module can be imported without side-effects
    from data_layer         import get_universe, get_ohlcv, get_earnings_data
    from feature_layer      import compute_features
    from trend_signals      import compute_position_context, save_trend_signals
    from signal_engine      import generate_signals, rank_signals_for_allocation
    from risk_engine        import enrich_signals
    from portfolio_engine   import size_signals, compute_portfolio_heat
    from production_parity  import (
        build_followthrough_addon_actions,
        filter_entry_signal_candidates,
        plan_entry_candidates,
        risk_pct_for_market_state,
    )
    from performance_engine import compute_metrics
    from report_generator   import generate_daily_report, save_report
    from universe_adapter   import save_universe_state_report, universe_segments_as_of
    from portfolio_accounting import resolve_portfolio_accounting
    from candidate_competition_logger import summarize_pilot_competition
    from pilot_sleeve       import (
        append_pilot_decision_snapshots,
        apply_pilot_sizing_policy,
        build_counterfactual_snapshots,
        mark_pilot_signals,
        pilot_governance_metadata,
        pilot_records_as_of,
        select_pilot_entry_candidates,
    )

    open_positions    = _load_open_positions()
    _stored_pv        = (open_positions or {}).get("portfolio_value_usd")
    portfolio_value   = _stored_pv          # updated below after OHLCV is available
    universe          = get_universe()
    log.info(f"Universe ({len(universe)} tickers): {universe}")
    universe_governance_state = None
    pilot_records = {}
    pilot_universe = []
    pilot_metadata = {}
    try:
        today_iso = datetime.now().date().isoformat()
        universe_governance_state = universe_segments_as_of(
            today_iso,
            core_universe=universe,
        )
        save_universe_state_report(
            universe_governance_state,
            f"data/universe_state_{today}.json",
        )
        pilot_records = pilot_records_as_of(today_iso)
        pilot_universe = sorted(set(pilot_records) - set(universe))
        pilot_metadata = pilot_governance_metadata()
        if pilot_universe:
            universe_governance_state["mode"] = "production_pilot_sleeve"
            universe_governance_state["production_impact"] = {
                "alters_signal_generation": True,
                "alters_candidate_ranking": False,
                "alters_sizing": True,
                "alters_orders": True,
                "scope": "pilot_sleeve_only",
            }
            universe_governance_state["pilot_trade_universe"] = pilot_universe
            save_universe_state_report(
                universe_governance_state,
                f"data/universe_state_{today}.json",
            )
        log.info(
            "Universe governance: core=%s pilot=%s trade-enabled-pilot=%s research=%s specialist=%s quarantine=%s",
            len(universe_governance_state["core_trade_universe"]),
            len(universe_governance_state["segments"]["pilot"]),
            len(pilot_universe),
            len(universe_governance_state["segments"]["research"]),
            len(universe_governance_state["segments"]["specialist"]),
            len(universe_governance_state["segments"]["quarantine"]),
        )
        if pilot_universe:
            log.info("Pilot sleeve trade-enabled tickers: %s", pilot_universe)
    except Exception as e:
        log.warning(f"Universe governance adapter unavailable: {e}")

    # ── Step 2: Market Regime ─────────────────────────────────────────────────
    _print_section("STEP 2 — Market regime")
    try:
        from regime import compute_market_regime
        market_regime = compute_market_regime()
        log.info(f"Regime: {market_regime['regime']}")
    except Exception as e:
        log.warning(f"Regime unavailable: {e}")
        market_regime = {"regime": "UNKNOWN", "note": str(e), "indices": {}}

    # ── Step 3: OHLCV + Earnings (single download per ticker) ────────────────
    _print_section("STEP 3 — OHLCV + earnings data")
    ohlcv_dict    = {}
    earnings_dict = {}
    data_universe = sorted(set(universe) | set(pilot_universe))
    for ticker in data_universe:
        ohlcv_dict[ticker]    = get_ohlcv(ticker)        # 350 calendar days
        earnings_dict[ticker] = get_earnings_data(ticker)
    spy_ohlcv = ohlcv_dict.get("SPY")
    if spy_ohlcv is None:
        spy_ohlcv = get_ohlcv("SPY")

    # P-ERN: persist today's earnings snapshot so backtester can reconstruct
    # eps_estimate and avg_historical_surprise_pct for earnings_event_long.
    # Without this snapshot, the backtester uses None for both fields, capping
    # C-strategy confidence at 0.83 and preventing quality filtering.
    persist_earnings_snapshot(earnings_dict, as_of=datetime.now(), logger=log)

    # ── Step 4: Feature Layer ─────────────────────────────────────────────────
    _print_section("STEP 4 — Feature layer")
    features_dict = {}
    for ticker in data_universe:
        features_dict[ticker] = compute_features(
            ticker, ohlcv_dict[ticker], earnings_dict[ticker]
        )
    ok = sum(1 for f in features_dict.values() if f)
    log.info(f"Features ready: {ok}/{len(data_universe)} tickers")

    # ── Live portfolio value ─────────────────────────────────────────────────
    # If cash_usd is omitted, derive it from portfolio_value_usd - live equity.
    # This avoids daily manual cash maintenance while keeping sizing accurate.
    if open_positions and open_positions.get("positions"):
        _current_px = {
            t: f["close"] for t, f in features_dict.items()
            if f and f.get("close") is not None
        }
        _accounting = resolve_portfolio_accounting(
            open_positions,
            _current_px,
            stored_portfolio_value=_stored_pv,
            logger=log,
        )
        if _accounting.get("portfolio_value_usd"):
            portfolio_value = _accounting["portfolio_value_usd"]
            log.info(
                "Portfolio value: $%s (%s; equity=$%s cash=$%s)",
                f"{portfolio_value:,.0f}",
                _accounting["cash_source"],
                f"{_accounting['equity_market_value_usd']:,.0f}",
                (
                    f"{_accounting['cash_usd']:,.0f}"
                    if _accounting.get("cash_usd") is not None else "n/a"
                ),
            )
    else:
        if portfolio_value:
            log.info(f"Portfolio value: ${portfolio_value:,.0f} (stored, no positions)")

    # ── Step 5: Position context (exit signals for held tickers) ─────────────
    _print_section("STEP 5 — Position context")
    # Build trend_signals dict with key names that llm_advisor.build_prompt() expects:
    #   breakout_20d → breakout,  breakdown_20d → breakdown,
    #   high_20d     → 20d_high,  low_20d       → 20d_low
    trend_signals_signals = {}
    for ticker, f in features_dict.items():
        if f is None:
            continue
        sig = {
            "close":            f["close"],
            "20d_high":         f["high_20d"],
            "20d_low":          f["low_20d"],
            "breakout":         f["breakout_20d"],
            "breakdown":        f["breakdown_20d"],
            "atr":              f.get("atr"),
            # Bonus keys for LLM context (not required by build_prompt, but useful)
            "above_200ma":      f.get("above_200ma"),
            "momentum_10d_pct": f.get("momentum_10d_pct"),
            "volume_spike":     f.get("volume_spike"),
            "trend_score":      f.get("trend_score"),
            "days_to_earnings": f.get("days_to_earnings"),
        }
        # Compute prev_close for daily_return_pct (post-earnings gap detection).
        # Required by LLM rules: "daily_return_pct > +8% → REDUCE 50%", "< -5% → EXIT".
        # Without this the LLM cannot distinguish a single-day gap from cumulative PnL.
        ohlcv = ohlcv_dict.get(ticker)
        prev_close = None
        if ohlcv is not None and len(ohlcv) >= 2:
            try:
                prev_val   = ohlcv['Close'].iloc[-2]
                prev_close = float(prev_val.item() if hasattr(prev_val, 'item') else prev_val)
            except Exception:
                pass

        # Compute high_since_entry for accurate trailing stop high-water mark.
        # Bug: without this, trailing stop uses 20d high, missing peaks from >20 days ago.
        # Example: stock peaked at $150 (35d ago), high_20d=$142 → trailing=$130.64 (wrong);
        # high_since_entry=$150 → trailing=$138.00 (correct, would have triggered).
        high_since_entry = None
        if open_positions and ohlcv is not None:
            for pos in open_positions.get('positions', []):
                if pos.get('ticker') == ticker:
                    entry_date_str = pos.get('entry_date')
                    if entry_date_str:
                        try:
                            entry_dt    = pd.Timestamp(entry_date_str)
                            data_since  = ohlcv[ohlcv.index >= entry_dt]
                            if not data_since.empty:
                                raw_high         = data_since['High'].max()
                                high_since_entry = float(
                                    raw_high.item() if hasattr(raw_high, 'item') else raw_high
                                )
                        except Exception:
                            pass
                    break

        # Add exit-level position context for held tickers
        pos_ctx = compute_position_context(
            ticker, f["close"], open_positions,
            atr=f.get("atr"),
            high_20d=f.get("high_20d"),
            high_since_entry=high_since_entry,
            prev_close=prev_close,
        )
        if pos_ctx:
            sig["position"] = pos_ctx
            log.info(f"{ticker}: position context added "
                     f"(urgency={pos_ctx['exit_signals']['high_urgency']})")

        trend_signals_signals[ticker] = sig

    trend_signals_dict = {
        "generated_at": datetime.now().isoformat(),
        "asof_date":    datetime.now().strftime("%Y-%m-%d"),
        "universe":     universe,
        "pilot_universe": pilot_universe,
        "data_universe": data_universe,
        "market_regime": market_regime,
        "signals":      trend_signals_signals,
    }

    # Save trend signals JSON (backward-compatible output)
    # quant_signals will be attached after Step 6 enrichment
    trend_output = f"data/trend_signals_{today}.json"
    save_trend_signals(trend_signals_dict, trend_output)

    # ── Step 6: Quant signals ─────────────────────────────────────────────────
    _print_section("STEP 6 — Quant signals")

    # Build market_context: regime + RS filter + pct_from_ma for BEAR tier detection.
    spy_10d         = market_regime.get("indices", {}).get("SPY", {}).get("momentum_10d_pct")
    qqq_10d         = market_regime.get("indices", {}).get("QQQ", {}).get("momentum_10d_pct")
    spy_pct_from_ma = market_regime.get("indices", {}).get("SPY", {}).get("pct_from_ma")
    qqq_pct_from_ma = market_regime.get("indices", {}).get("QQQ", {}).get("pct_from_ma")
    market_context  = {
        "market_regime":   market_regime.get("regime", "UNKNOWN"),
        "spy_10d_return":  spy_10d,
        "qqq_10d_return":  qqq_10d,
        "spy_pct_from_ma": spy_pct_from_ma,
        "qqq_pct_from_ma": qqq_pct_from_ma,
    }
    if spy_10d is not None:
        log.info(f"SPY 10d return: {spy_10d*100:.2f}% (RS filter active)")
    if spy_pct_from_ma is not None and qqq_pct_from_ma is not None:
        log.info(f"SPY vs 200MA: {spy_pct_from_ma*100:+.2f}%   "
                 f"QQQ vs 200MA: {qqq_pct_from_ma*100:+.2f}%")

    core_features_dict = {
        ticker: features_dict.get(ticker)
        for ticker in universe
        if ticker in features_dict
    }
    pilot_features_dict = {
        ticker: features_dict.get(ticker)
        for ticker in pilot_universe
        if ticker in features_dict
    }

    signals = generate_signals(
        core_features_dict,
        market_context=market_context,
        enabled_strategies=ENABLED_STRATEGIES,
        breakout_max_pullback_from_52w_high=BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
    )
    if BREAKOUT_RANK_BY_52W_HIGH:
        signals = rank_signals_for_allocation(signals)
    exit_profile = compute_regime_exit_profile(market_context, base_target_mult=ATR_TARGET_MULT)
    atr_target_mult = exit_profile["target_mult"] if REGIME_AWARE_EXIT else ATR_TARGET_MULT
    if REGIME_AWARE_EXIT:
        log.info(
            "Regime-aware exit active: "
            f"bucket={exit_profile['bucket']} score={exit_profile['score']} "
            f"target_mult={atr_target_mult:.2f}"
        )
    signals = enrich_signals(signals, features_dict, atr_target_mult=atr_target_mult)
    if REGIME_AWARE_EXIT:
        for s in signals:
            s["target_mult_used"] = exit_profile["target_mult"]
            s["regime_exit_bucket"] = exit_profile["bucket"]
            s["regime_exit_score"] = exit_profile["score"]

    signals, entry_filter_audit = filter_entry_signal_candidates(
        signals,
        open_positions=open_positions,
        market_regime=market_regime.get("regime", "").upper(),
        spy_pct_from_ma=spy_pct_from_ma,
        qqq_pct_from_ma=qqq_pct_from_ma,
    )
    if entry_filter_audit["already_held_dropped"]:
        log.info(
            "Already-held filter: dropped %s",
            [s["ticker"] for s in entry_filter_audit["already_held_dropped"]],
        )
    for s in entry_filter_audit["sector_cap_dropped"]:
        log.warning(
            "%s: dropped by sector cap for sector '%s'",
            s.get("ticker"),
            s.get("sector", "Unknown"),
        )
    if entry_filter_audit["bear_shallow_active"]:
        log.info(
            "BEAR_SHALLOW filter: %d -> %d signals",
            entry_filter_audit["signals_before_entry_filters"],
            entry_filter_audit["signals_after_entry_filters"],
        )
    # Surface any signals dropped during enrichment (ATR missing, R:R too low)
    from risk_engine import last_dropped_signals
    if last_dropped_signals:
        log.warning(
            f"Dropped {len(last_dropped_signals)} signal(s) during enrichment: "
            + "; ".join(f"{d['ticker']} — {d['reason']}" for d in last_dropped_signals)
        )

    _regime_str = market_regime.get("regime", "").upper()

    log.info(f"Signals generated: {len(signals)}")

    pilot_signals = []
    pilot_entry_filter_audit = {
        "signals_before_entry_filters": 0,
        "signals_after_entry_filters": 0,
        "already_held_dropped": [],
        "sector_cap_dropped": [],
        "bear_shallow_dropped": [],
    }
    if pilot_features_dict:
        pilot_signals = generate_signals(
            pilot_features_dict,
            market_context=market_context,
            enabled_strategies=ENABLED_STRATEGIES,
            breakout_max_pullback_from_52w_high=BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
        )
        if BREAKOUT_RANK_BY_52W_HIGH:
            pilot_signals = rank_signals_for_allocation(pilot_signals)
        pilot_signals = enrich_signals(
            pilot_signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        if REGIME_AWARE_EXIT:
            for s in pilot_signals:
                s["target_mult_used"] = exit_profile["target_mult"]
                s["regime_exit_bucket"] = exit_profile["bucket"]
                s["regime_exit_score"] = exit_profile["score"]
        pilot_signals = mark_pilot_signals(
            pilot_signals,
            pilot_records,
            metadata=pilot_metadata,
        )
        pilot_signals, pilot_entry_filter_audit = filter_entry_signal_candidates(
            pilot_signals,
            open_positions=open_positions,
            market_regime=market_regime.get("regime", "").upper(),
            spy_pct_from_ma=spy_pct_from_ma,
            qqq_pct_from_ma=qqq_pct_from_ma,
        )
        log.info(f"Pilot sleeve signals generated: {len(pilot_signals)}")

    _trade_risk_pct = risk_pct_for_market_state(
        _regime_str,
        spy_pct_from_ma=spy_pct_from_ma,
        qqq_pct_from_ma=qqq_pct_from_ma,
    )
    if _trade_risk_pct is not None:
        log.info("Regime-adjusted position sizing: %.2f%% risk per trade", _trade_risk_pct * 100)

    # Current prices for heat + sizing
    current_prices = {
        t: f["close"] for t, f in features_dict.items() if f and f.get("close")
    }

    portfolio_heat = None
    heat_blocked_signals = []
    heat_blocked_pilot_signals = []
    if open_positions and portfolio_value:
        # Pass features_dict so heat uses effective stops (ATR/trailing) not just avg_cost stop
        portfolio_heat = compute_portfolio_heat(
            open_positions, current_prices, portfolio_value,
            features_dict=features_dict
        )
        log.info(portfolio_heat["heat_note"])
        if portfolio_heat["can_add_new_positions"] and portfolio_value:
            signals = size_signals(signals, portfolio_value, risk_pct=_trade_risk_pct)
            pilot_signals = size_signals(
                pilot_signals,
                portfolio_value,
                risk_pct=_trade_risk_pct,
            )
        else:
            heat_blocked_signals = signals
            heat_blocked_pilot_signals = pilot_signals
            signals = []
            pilot_signals = []
    elif portfolio_value:
        signals = size_signals(signals, portfolio_value, risk_pct=_trade_risk_pct)
        pilot_signals = size_signals(
            pilot_signals,
            portfolio_value,
            risk_pct=_trade_risk_pct,
        )

    signals, entry_execution_plan = plan_entry_candidates(
        signals,
        open_positions,
        market_context=market_context,
    )
    pilot_signals = apply_pilot_sizing_policy(pilot_signals, pilot_records)
    pilot_signals, pilot_entry_execution_plan = select_pilot_entry_candidates(
        pilot_signals,
        pilot_records,
        open_positions=open_positions,
    )
    pilot_decision_snapshots = build_counterfactual_snapshots(
        pilot_signals,
        core_signals=signals,
        as_of=datetime.now().date().isoformat(),
        market_context=market_context,
        portfolio_heat=portfolio_heat,
        metadata=pilot_metadata,
    )
    pilot_decision_hashes = []
    if pilot_decision_snapshots:
        try:
            pilot_decision_hashes = append_pilot_decision_snapshots(
                pilot_decision_snapshots
            )
            for sig, snapshot, decision_hash in zip(
                pilot_signals,
                pilot_decision_snapshots,
                pilot_decision_hashes,
            ):
                sig.setdefault("pilot_sleeve", {})["decision_id"] = snapshot["decision_id"]
                sig.setdefault("pilot_sleeve", {})["decision_hash"] = decision_hash
            log.info(
                "Pilot sleeve pre-trade snapshots logged: %s",
                pilot_decision_hashes,
            )
        except Exception as e:
            log.error(f"Pilot sleeve decision snapshot logging failed: {e}")
    if entry_execution_plan["deferred_breakout_signals"]:
        log.info(
            "Scarce-slot routing deferred %d breakout signal(s)",
            len(entry_execution_plan["deferred_breakout_signals"]),
        )
    if entry_execution_plan["slot_sliced_signals"]:
        log.info(
            "Position slots kept %d/%d signal(s)",
            entry_execution_plan["signals_after_entry_plan"],
            entry_execution_plan["signals_before_entry_plan"],
        )

    addon_ohlcv_dict = dict(ohlcv_dict)
    addon_ohlcv_dict["SPY"] = spy_ohlcv
    addon_actions, addon_audit = build_followthrough_addon_actions(
        open_positions=open_positions,
        ohlcv_dict=addon_ohlcv_dict,
        portfolio_value=portfolio_value,
        current_prices=current_prices,
        portfolio_heat=portfolio_heat,
    )
    if addon_actions:
        log.info(
            "Follow-through add-ons: %s",
            ", ".join(
                f"{a['ticker']} +{a['shares_to_buy']}" for a in addon_actions
            ),
        )

    metrics = compute_metrics()
    pilot_attribution = summarize_pilot_competition(sleeve="AI_INFRA_PILOT")
    if pilot_attribution.get("outcome_records"):
        log.info(
            "Pilot attribution: outcomes=%s direct_pnl=$%s replacement_value=%s pending=%s",
            pilot_attribution.get("outcome_records"),
            pilot_attribution.get("direct_pilot_pnl"),
            pilot_attribution.get("replacement_value"),
            pilot_attribution.get("pending_replacement_outcomes"),
        )

    # Attach enriched quant signals to trend_signals_dict so llm_advisor can show
    # pre-computed target_price, risk_reward_ratio, trade_quality_score, strategy.
    trend_signals_dict["quant_signals"] = signals
    trend_signals_dict["pilot_quant_signals"] = pilot_signals
    trend_signals_dict["addon_actions"] = addon_actions
    trend_signals_dict["entry_filter_audit"] = entry_filter_audit
    trend_signals_dict["entry_execution_plan"] = entry_execution_plan
    trend_signals_dict["pilot_entry_filter_audit"] = pilot_entry_filter_audit
    trend_signals_dict["pilot_entry_execution_plan"] = pilot_entry_execution_plan
    trend_signals_dict["pilot_decision_hashes"] = pilot_decision_hashes
    trend_signals_dict["pilot_attribution"] = pilot_attribution

    # ── Step 7: Quant report ──────────────────────────────────────────────────
    _print_section("STEP 7 — Quant report")
    report = generate_daily_report(
        signals          = signals,
        features_dict    = features_dict,
        portfolio_heat   = portfolio_heat,
        metrics          = metrics,
        market_regime    = market_regime,
        open_positions   = open_positions,
        dropped_signals  = last_dropped_signals or None,
        addon_actions    = addon_actions,
        entry_execution_plan = entry_execution_plan,
        pilot_attribution = pilot_attribution,
    )
    print("\n" + report)
    save_report(report)

    _save_json({
        "generated_at":   datetime.now().isoformat(),
        "market_regime":  market_regime,
        "portfolio_heat": portfolio_heat,
        "signals":        signals,
        "pilot_signals":  pilot_signals,
        "addon_actions":  addon_actions,
        "addon_audit":    addon_audit,
        "entry_filter_audit": entry_filter_audit,
        "entry_execution_plan": entry_execution_plan,
        "pilot_entry_filter_audit": pilot_entry_filter_audit,
        "pilot_entry_execution_plan": pilot_entry_execution_plan,
        "pilot_decision_snapshots": pilot_decision_snapshots,
        "pilot_decision_hashes": pilot_decision_hashes,
        "pilot_attribution": pilot_attribution,
        "heat_blocked_signals": heat_blocked_signals,
        "heat_blocked_pilot_signals": heat_blocked_pilot_signals,
        "universe_governance": universe_governance_state,
        "features":       features_dict,
    }, f"data/quant_signals_{today}.json")

    # ── Step 8: Fetch & filter news ───────────────────────────────────────────
    _print_section("STEP 8 — News collection")
    trade_items = []
    try:
        from sources import get_all_sources
        from parser  import parse_feed, deduplicate_items, sort_items_by_date
        from filter  import apply_hygiene_filters, apply_trade_filters

        all_items  = []
        sources    = get_all_sources(extra_tickers=pilot_universe)
        log.info(f"Fetching from {len(sources)} RSS sources...")
        for source in sources:
            try:
                items = parse_feed(source["url"], source["source_type"],
                                   source.get("metadata", {}))
                all_items.extend(items)
            except Exception as e:
                log.warning(f"Source {source['url']}: {e}")

        sorted_items  = sort_items_by_date(deduplicate_items(all_items))
        hygiene_items = apply_hygiene_filters(sorted_items)["items"]
        trade_watchlist = sorted(set(universe) | set(pilot_universe))
        trade_items   = apply_trade_filters(
            sorted_items,
            watchlist=trade_watchlist,
        )["items"]

        _save_json(sorted_items,  f"data/news_{today}.json")
        _save_json(hygiene_items, f"data/clean_news_{today}.json")
        _save_json(trade_items,   f"data/clean_trade_news_{today}.json")

        log.info(f"News: {len(sorted_items)} raw → {len(hygiene_items)} hygiene "
                 f"→ {len(trade_items)} trade-filtered")
    except Exception as e:
        log.error(f"News collection failed: {e}")

    # ── Step 9: LLM prompt ────────────────────────────────────────────────────
    _print_section("STEP 9 — LLM prompt")
    # Always generate the prompt — quant signals and position management do not
    # require news. On news-quiet days the prompt still surfaces exit signals
    # and high-confidence quant signals that stand alone (confidence >= 0.85).
    #
    # P-LLM coverage note:
    #   If OPENAI_API_KEY is present, call the API and persist the dated advice file.
    #   llm_advisor.save_advice() mirrors that file to llm_prompt_resp_YYYYMMDD.json,
    #   which is what backtester --replay-llm consumes. Without this branch, the main
    #   daily pipeline only saves prompts and replay coverage never compounds.
    try:
        from llm_advisor import get_investment_advice, save_advice
        save_prompt_only = not bool(os.environ.get("OPENAI_API_KEY"))
        if save_prompt_only:
            log.info(
                "OPENAI_API_KEY not set — saving prompt only. "
                "Set OPENAI_API_KEY to auto-save dated advice + replay log."
            )
        result = get_investment_advice(
            trade_items,           # may be [] on quiet news days — that's fine
            open_positions = open_positions,
            trend_signals  = trend_signals_dict,
            save_prompt_only = save_prompt_only,
        )
        if result["success"]:
            log.info(result["advice"])
            if not save_prompt_only:
                advice_output = f"data/investment_advice_{today}.json"
                save_advice(result["advice"], advice_output, result["token_usage"])
        else:
            log.error(f"LLM advisor: {result['error']}")
    except Exception as e:
        log.error(f"LLM advisor failed: {e}")

    # ── Step 10: Summary ──────────────────────────────────────────────────────
    _print_section("PIPELINE COMPLETE")
    log.info(f"  Tickers analyzed:   {len(universe)}")
    log.info(f"  Signals generated:  {len(signals)}")
    log.info(f"  Pilot signals:      {len(pilot_signals)}")
    log.info(f"  Add-on actions:     {len(addon_actions)}")
    log.info(f"  News (trade):       {len(trade_items)}")
    log.info(f"  Regime:             {market_regime['regime']}")
    if portfolio_heat:
        log.info(f"  Portfolio heat:     {portfolio_heat['portfolio_heat_pct']*100:.1f}%")
    if metrics.get("total_trades", 0) > 0:
        log.info(f"  P&L (realized):     ${metrics['total_pnl_usd']:,.2f}  "
                 f"WR={metrics['win_rate']*100:.0f}%")
    log.info("")


if __name__ == "__main__":
    main()
