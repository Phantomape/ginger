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
    from signal_engine      import generate_signals
    from risk_engine        import enrich_signals
    from portfolio_engine   import size_signals, compute_portfolio_heat
    from performance_engine import compute_metrics
    from report_generator   import generate_daily_report, save_report
    from constants          import MAX_PER_SECTOR

    open_positions    = _load_open_positions()
    _stored_pv        = (open_positions or {}).get("portfolio_value_usd")
    portfolio_value   = _stored_pv          # updated below after OHLCV is available
    universe          = get_universe()
    log.info(f"Universe ({len(universe)} tickers): {universe}")

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
    for ticker in universe:
        ohlcv_dict[ticker]    = get_ohlcv(ticker)        # 350 calendar days
        earnings_dict[ticker] = get_earnings_data(ticker)

    # ── Step 4: Feature Layer ─────────────────────────────────────────────────
    _print_section("STEP 4 — Feature layer")
    features_dict = {}
    for ticker in universe:
        features_dict[ticker] = compute_features(
            ticker, ohlcv_dict[ticker], earnings_dict[ticker]
        )
    ok = sum(1 for f in features_dict.values() if f)
    log.info(f"Features ready: {ok}/{len(universe)} tickers")

    # ── Live portfolio value ─────────────────────────────────────────────────
    # open_positions.json portfolio_value_usd is user-maintained and can be stale.
    # Compute live PV from current_prices × shares to keep sizing accurate.
    if open_positions and open_positions.get("positions"):
        _current_px = {
            t: f["close"] for t, f in features_dict.items()
            if f and f.get("close") is not None
        }
        _equity = sum(
            pos.get("shares", 0) * _current_px.get(
                pos.get("ticker", ""), pos.get("avg_cost", 0)
            )
            for pos in open_positions["positions"]
            if pos.get("ticker") and pos.get("shares", 0) > 0
        )
        _cash_raw = open_positions.get("cash_usd")
        if _cash_raw is None:
            if _stored_pv:
                log.warning(
                    f"cash_usd missing — using stored portfolio_value_usd="
                    f"{_stored_pv:,.0f} for sizing"
                )
            log.info(f"Portfolio value: ${portfolio_value:,.0f} (stored)")
        else:
            _live_pv = _equity + _cash_raw
            if _live_pv > 0:
                if _stored_pv and abs(_live_pv - _stored_pv) / max(_stored_pv, 1) > 0.15:
                    log.warning(
                        f"Portfolio value drift: stored={_stored_pv:,.0f}  "
                        f"live={_live_pv:,.0f} USD — using live for sizing"
                    )
                portfolio_value = _live_pv
                log.info(f"Portfolio value: ${portfolio_value:,.0f} (live)")
            else:
                log.info(f"Portfolio value: ${portfolio_value:,.0f} (stored)")
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
    spy_pct_from_ma = market_regime.get("indices", {}).get("SPY", {}).get("pct_from_ma")
    qqq_pct_from_ma = market_regime.get("indices", {}).get("QQQ", {}).get("pct_from_ma")
    market_context  = {
        "market_regime":   market_regime.get("regime", "UNKNOWN"),
        "spy_10d_return":  spy_10d,
        "spy_pct_from_ma": spy_pct_from_ma,
        "qqq_pct_from_ma": qqq_pct_from_ma,
    }
    if spy_10d is not None:
        log.info(f"SPY 10d return: {spy_10d*100:.2f}% (RS filter active)")
    if spy_pct_from_ma is not None and qqq_pct_from_ma is not None:
        log.info(f"SPY vs 200MA: {spy_pct_from_ma*100:+.2f}%   "
                 f"QQQ vs 200MA: {qqq_pct_from_ma*100:+.2f}%")

    signals = generate_signals(features_dict, market_context=market_context)
    signals = enrich_signals(signals, features_dict)

    # ── Filter out tickers already held ──────────────────────────────────
    # Matches backtester.py:395 ("Skip if already holding") — without this,
    # production recommends buying more of a stock already in the portfolio.
    if open_positions and open_positions.get("positions"):
        _held = {p["ticker"] for p in open_positions["positions"] if p.get("ticker")}
        _before_held = len(signals)
        _dropped_held = [s for s in signals if s["ticker"] in _held]
        signals = [s for s in signals if s["ticker"] not in _held]
        if _dropped_held:
            log.info(
                f"Already-held filter: {_before_held} → {len(signals)} signals "
                f"(dropped {[s['ticker'] for s in _dropped_held]})"
            )

    # ── Same-day sector concentration cap ─────────────────────────────────
    # Multiple correlated signals can fire on the same day (e.g. 3 tech stocks).
    # Entering all of them turns 3 independent 1% risks into one concentrated bet.
    # Cap at 2 signals per sector; signals are already sorted by confidence from
    # generate_signals(), so the top-2 per sector survive.
    _sector_counts: dict[str, int] = {}
    _capped_signals = []
    _dropped_sector = []
    for s in signals:
        sec = s.get("sector", "Unknown")
        _sector_counts[sec] = _sector_counts.get(sec, 0) + 1
        if _sector_counts[sec] <= MAX_PER_SECTOR:
            _capped_signals.append(s)
        else:
            _dropped_sector.append(s)
            log.warning(
                f"{s['ticker']}: dropped — sector '{sec}' already has "
                f"{MAX_PER_SECTOR} signals today"
            )
    if _dropped_sector:
        log.info(
            f"Sector cap: {len(signals)} → {len(_capped_signals)} signals "
            f"(dropped {len(_dropped_sector)} for concentration)"
        )
    signals = _capped_signals

    # Surface any signals dropped during enrichment (ATR missing, R:R too low)
    from risk_engine import last_dropped_signals
    if last_dropped_signals:
        log.warning(
            f"Dropped {len(last_dropped_signals)} signal(s) during enrichment: "
            + "; ".join(f"{d['ticker']} — {d['reason']}" for d in last_dropped_signals)
        )

    # ── BEAR_SHALLOW post-enrich filter ──────────────────────────────────────
    # signal_engine already drops BEAR_DEEP (both ≤ -5%) and individual tickers
    # that are below their own 200MA.  After enrich_signals adds sector and TQS,
    # apply the two remaining BEAR_SHALLOW gates:
    #   1. Sector allowlist: Commodities + Healthcare only (negative-beta to tech BEAR)
    #   2. TQS ≥ 0.75: stricter quality bar to compensate for elevated macro risk
    _regime_str = market_regime.get("regime", "").upper()
    if (_regime_str == "BEAR"
            and spy_pct_from_ma is not None
            and qqq_pct_from_ma is not None
            and min(spy_pct_from_ma, qqq_pct_from_ma) > -0.05):
        _BEAR_SHALLOW_SECTORS = {"Commodities", "Healthcare"}
        _before = len(signals)
        signals = [
            s for s in signals
            if s.get("sector") in _BEAR_SHALLOW_SECTORS
            and (s.get("trade_quality_score") or 0) >= 0.75
        ]
        log.info(
            f"BEAR_SHALLOW filter: {_before} → {len(signals)} signals "
            f"(Commodities+Healthcare only, TQS≥0.75)"
        )

    log.info(f"Signals generated: {len(signals)}")

    # ── Regime-adjusted risk per trade ───────────────────────────────────────
    # Scale down position sizing in adverse regimes to reduce portfolio heat
    # while keeping the trade structure (R:R, stop, target) unchanged.
    #   BULL         : 1.00% (default)
    #   NEUTRAL      : 0.75% — mixed market; reduce exposure, keep selectivity
    #   BEAR_SHALLOW : 0.50% — both below MA; defensive-sector-only exposure
    #   BEAR_DEEP    : N/A   — no signals generated
    if _regime_str == "NEUTRAL":
        _trade_risk_pct = 0.0075
        log.info("NEUTRAL regime: position sizing at 0.75% risk per trade")
    elif (_regime_str == "BEAR"
          and spy_pct_from_ma is not None
          and qqq_pct_from_ma is not None
          and min(spy_pct_from_ma, qqq_pct_from_ma) > -0.05):
        _trade_risk_pct = 0.005
        log.info("BEAR_SHALLOW regime: position sizing at 0.50% risk per trade")
    else:
        _trade_risk_pct = None   # use portfolio_engine default (1.0%)

    # Current prices for heat + sizing
    current_prices = {
        t: f["close"] for t, f in features_dict.items() if f and f.get("close")
    }

    portfolio_heat = None
    if open_positions and portfolio_value:
        # Pass features_dict so heat uses effective stops (ATR/trailing) not just avg_cost stop
        portfolio_heat = compute_portfolio_heat(
            open_positions, current_prices, portfolio_value,
            features_dict=features_dict
        )
        log.info(portfolio_heat["heat_note"])
        if portfolio_heat["can_add_new_positions"] and portfolio_value:
            signals = size_signals(signals, portfolio_value, risk_pct=_trade_risk_pct)
    elif portfolio_value:
        signals = size_signals(signals, portfolio_value, risk_pct=_trade_risk_pct)

    metrics = compute_metrics()

    # Attach enriched quant signals to trend_signals_dict so llm_advisor can show
    # pre-computed target_price, risk_reward_ratio, trade_quality_score, strategy.
    trend_signals_dict["quant_signals"] = signals

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
    )
    print("\n" + report)
    save_report(report)

    _save_json({
        "generated_at":   datetime.now().isoformat(),
        "market_regime":  market_regime,
        "portfolio_heat": portfolio_heat,
        "signals":        signals,
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
        sources    = get_all_sources()
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
        trade_items   = apply_trade_filters(sorted_items)["items"]

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
    try:
        from llm_advisor import get_investment_advice, save_advice
        result = get_investment_advice(
            trade_items,           # may be [] on quiet news days — that's fine
            open_positions = open_positions,
            trend_signals  = trend_signals_dict,
            save_prompt_only = True,   # saves to data/llm_prompt_YYYYMMDD.txt
        )
        if result["success"]:
            log.info(result["advice"])
        else:
            log.error(f"LLM advisor: {result['error']}")
    except Exception as e:
        log.error(f"LLM advisor failed: {e}")

    # ── Step 10: Summary ──────────────────────────────────────────────────────
    _print_section("PIPELINE COMPLETE")
    log.info(f"  Tickers analyzed:   {len(universe)}")
    log.info(f"  Signals generated:  {len(signals)}")
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
