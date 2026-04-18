#!/usr/bin/env python3
"""
Unified news collection and filtering pipeline.

This script combines news fetching, filtering, and LLM analysis into a single command:
1. Fetches news from all RSS sources
2. Applies hygiene filtering
3. Applies trade-focused filtering
4. Gets investment advice from OpenAI (requires OPENAI_API_KEY env var)
5. Saves all outputs

Usage:
    export OPENAI_API_KEY=your_api_key_here
    python run_pipeline.py
"""

import json
import logging
import os
import sys
from datetime import datetime

from sources import get_all_sources
from parser import parse_feed, deduplicate_items, sort_items_by_date
from filter import apply_hygiene_filters, apply_trade_filters
from llm_advisor import get_investment_advice, save_advice
from trend_signals import generate_trend_signals, save_trend_signals


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_all_news():
    """
    Fetch news from all sources and return normalized items.

    Returns:
        list: List of all news items from all sources
    """
    all_items = []
    sources = get_all_sources()

    logger.info(f"Starting news collection from {len(sources)} sources")

    for source in sources:
        url = source["url"]
        source_type = source["source_type"]
        metadata = source.get("metadata", {})

        try:
            items = parse_feed(url, source_type, metadata)
            all_items.extend(items)
        except Exception as e:
            logger.error(f"Failed to process source {url}: {e}")
            # Continue with other sources
            continue

    logger.info(f"Collected {len(all_items)} total items before deduplication")
    return all_items


def save_to_file(items, filepath):
    """
    Save news items to a JSON file.

    Args:
        items (list): List of news items to save
        filepath (str): Path to save the file

    Returns:
        bool: True if successful
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(items)} items to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save file {filepath}: {e}")
        return False


def print_stats(stats, title):
    """
    Print filtering statistics in a readable format.

    Args:
        stats (dict): Statistics dictionary
        title (str): Title for the stats section
    """
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print(f"  Input items:                {stats['input_count']}")
    print(f"  Dropped (old):              {stats['dropped_old']}")
    print(f"  Dropped (no tickers):       {stats['dropped_no_tickers']}")

    if "dropped_not_in_watchlist" in stats:
        print(f"  Dropped (not in watchlist): {stats['dropped_not_in_watchlist']}")
    if "dropped_no_event_keywords" in stats:
        print(f"  Dropped (no event keywords): {stats['dropped_no_event_keywords']}")

    print(f"  Dropped (duplicates):       {stats['dropped_duplicates']}")
    print(f"  Output items:               {stats['output_count']}")
    print("=" * 60)
    print()


def _validate_open_positions():
    """
    Validate open_positions.json for fields required by exit rules.
    Prints actionable console warnings (not just log entries) when fields are missing.

    Missing fields and their consequences:
      entry_date   → TIME_STOP (45-day stagnation rule) DISABLED
                     trailing stop HWM degrades to 20d-high (may miss peaks >20 days ago)
      target_price → SIGNAL_TARGET (3.5×ATR partial-exit at R:R target) DISABLED
                     +7% to +20% zone has no exit guidance; winners evaporate
    """
    for path in [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'open_positions.json'),
        'data/open_positions.json',
    ]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    positions_data = json.load(f)
                positions = positions_data.get('positions', [])

                missing_entry_date   = [p['ticker'] for p in positions
                                        if p.get('ticker') and not p.get('entry_date')]
                missing_target_price = [p['ticker'] for p in positions
                                        if p.get('ticker') and not p.get('target_price')]
                missing_override_after_profit = []
                for p in positions:
                    avg_cost = p.get('avg_cost', 0)
                    if avg_cost > 0 and not p.get('override_stop_price'):
                        # We can't compute current price here; flag positions where
                        # notes suggest a past PROFIT_TARGET trigger (heuristic only)
                        notes = (p.get('risk_notes') or '').lower()
                        if any(k in notes for k in ('profit', 'target', 'reduce', '止盈')):
                            missing_override_after_profit.append(p['ticker'])

                if missing_entry_date or missing_target_price:
                    print()
                    print("!" * 60)
                    print("  ⚠  OPEN POSITIONS: MISSING REQUIRED FIELDS")
                    print("!" * 60)
                    if missing_entry_date:
                        print(f"  TIME_STOP DISABLED for: {missing_entry_date}")
                        print("  → Add \"entry_date\": \"YYYY-MM-DD\" to each position")
                        print("    (45-day stagnation rule cannot fire; trailing stop")
                        print("     high-water mark degrades to 20-day high)")
                    if missing_target_price:
                        print(f"  SIGNAL_TARGET DISABLED for: {missing_target_price}")
                        print("  → Add \"target_price\": <value from 3a signal's target_price>")
                        print("    (3.5×ATR partial-exit cannot fire; +7%–+20% zone has")
                        print("     no exit guidance and winners may evaporate)")
                    print("!" * 60)
                    print()

            except Exception as e:
                logger.warning(f"Could not validate open_positions.json: {e}")
            break


def main():
    """
    Main function to run the complete news pipeline.
    """
    print()
    print("=" * 60)
    print("  NEWS COLLECTION & FILTERING PIPELINE")
    print("=" * 60)
    print()

    # Validate open positions fields before running — missing fields silently
    # disable exit rules (TIME_STOP, SIGNAL_TARGET).  Print console warnings so
    # users see the issue even without reading the LLM prompt JSON.
    _validate_open_positions()

    # Generate filenames with today's date
    today = datetime.now().strftime("%Y%m%d")
    raw_output = f"data/news_{today}.json"
    hygiene_output = f"data/clean_news_{today}.json"
    trade_output = f"data/clean_trade_news_{today}.json"

    try:
        # =====================================================
        # STEP 1: FETCH NEWS
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 1: Fetching News from RSS Sources")
        logger.info("=" * 60)

        all_items = fetch_all_news()

        if not all_items:
            logger.warning("No news items collected")
            return 1

        # Deduplicate by (title + url)
        unique_items = deduplicate_items(all_items)

        # Sort by date (newest first)
        sorted_items = sort_items_by_date(unique_items)

        # Save raw news
        if not save_to_file(sorted_items, raw_output):
            logger.error("Failed to save raw news")
            return 1

        logger.info("=" * 60)
        logger.info(f"Raw news saved: {len(sorted_items)} items")
        logger.info("=" * 60)

        # =====================================================
        # STEP 2: HYGIENE FILTERING
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 2: Applying Hygiene Filters")
        logger.info("=" * 60)

        hygiene_result = apply_hygiene_filters(sorted_items)
        hygiene_items = hygiene_result["items"]
        hygiene_stats = hygiene_result["stats"]

        # Save hygiene-filtered news
        if not save_to_file(hygiene_items, hygiene_output):
            logger.error("Failed to save hygiene-filtered news")
            return 1

        print_stats(hygiene_stats, "Hygiene Filtering Results")

        # =====================================================
        # STEP 3: TRADE FILTERING
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 3: Applying Trade-Focused Filters")
        logger.info("=" * 60)

        trade_result = apply_trade_filters(sorted_items)
        trade_items = trade_result["items"]
        trade_stats = trade_result["stats"]

        # Save trade-filtered news
        if not save_to_file(trade_items, trade_output):
            logger.error("Failed to save trade-filtered news")
            return 1

        print_stats(trade_stats, "Trade Filtering Results")

        # =====================================================
        # STEP 4: SIGNAL GENERATION (quant pipeline + position context)
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 4: Generating Signals (quant pipeline + position context)")
        logger.info("=" * 60)

        trend_output = f"data/trend_signals_{today}.json"
        trend_signals = None

        try:
            # Run the legacy trend_signals pipeline for position context
            # (exit levels, trailing stops, drawdown alerts for held positions).
            trend_signals = generate_trend_signals()

            # Run the full quant pipeline to get strategy A/B/C signals with
            # TQS, R:R, and risk enrichment — these are what the LLM needs under
            # "3a) 量化信号".  The llm_advisor looks for the key "quant_signals".
            try:
                from data_layer    import get_universe, get_ohlcv, get_earnings_data
                from feature_layer import compute_features
                from signal_engine import generate_signals
                from risk_engine   import enrich_signals
                from portfolio_engine import size_signals
                from regime        import compute_market_regime

                qp_universe = get_universe()
                qp_ohlcv    = {t: get_ohlcv(t)          for t in qp_universe}
                qp_earnings = {t: get_earnings_data(t)   for t in qp_universe}
                qp_features = {t: compute_features(t, qp_ohlcv[t], qp_earnings[t])
                               for t in qp_universe}

                qp_regime   = compute_market_regime()
                _spy_data = qp_regime.get("indices", {}).get("SPY", {})
                _qqq_data = qp_regime.get("indices", {}).get("QQQ", {})
                mc = {
                    "market_regime":   qp_regime.get("regime", ""),
                    "spy_10d_return":  _spy_data.get("momentum_10d_pct"),
                    "spy_pct_from_ma": _spy_data.get("pct_from_ma"),
                    "qqq_pct_from_ma": _qqq_data.get("pct_from_ma"),
                }

                qp_signals = generate_signals(qp_features, market_context=mc)
                qp_signals = enrich_signals(qp_signals, qp_features)

                # ── BEAR_SHALLOW post-enrich filter (mirrors run.py) ─────────
                _regime_str = qp_regime.get("regime", "").upper()
                _spy_pct = mc.get("spy_pct_from_ma")
                _qqq_pct = mc.get("qqq_pct_from_ma")
                if (_regime_str == "BEAR"
                        and _spy_pct is not None and _qqq_pct is not None
                        and min(_spy_pct, _qqq_pct) > -0.05):
                    _BEAR_SHALLOW_SECTORS = {"Commodities", "Healthcare"}
                    _before = len(qp_signals)
                    qp_signals = [
                        s for s in qp_signals
                        if s.get("sector") in _BEAR_SHALLOW_SECTORS
                        and (s.get("trade_quality_score") or 0) >= 0.75
                    ]
                    logger.info(
                        f"BEAR_SHALLOW filter: {_before} → {len(qp_signals)} signals "
                        f"(Commodities+Healthcare only, TQS≥0.75)"
                    )

                # ── Regime-adjusted risk per trade ───────────────────────────
                if _regime_str == "NEUTRAL":
                    _trade_risk_pct = 0.0075
                elif (_regime_str == "BEAR"
                      and _spy_pct is not None and _qqq_pct is not None
                      and min(_spy_pct, _qqq_pct) > -0.05):
                    _trade_risk_pct = 0.005
                else:
                    _trade_risk_pct = None   # default 1.0%

                # Add position sizing using LIVE portfolio value (not stored value).
                # open_positions.json portfolio_value_usd can be stale by months;
                # using it causes persistent under-sizing (e.g. stored=$100k,
                # live=$150k → shares sized for 0.67% risk instead of 1%).
                from llm_advisor import load_open_positions as _load_pos
                _open_pos = _load_pos()
                _stored_pv = (_open_pos or {}).get("portfolio_value_usd")
                _pv = _stored_pv
                if _open_pos and _open_pos.get("positions"):
                    _current_prices = {
                        t: f["close"]
                        for t, f in qp_features.items()
                        if f and f.get("close") is not None
                    }
                    _equity_pv = sum(
                        pos.get("shares", 0) * _current_prices.get(
                            pos.get("ticker", ""), pos.get("avg_cost", 0)
                        )
                        for pos in _open_pos["positions"]
                        if pos.get("ticker") and pos.get("shares", 0) > 0
                    )
                    _cash_raw = _open_pos.get("cash_usd")
                    if _cash_raw is None:
                        if _stored_pv:
                            logger.warning(
                                f"cash_usd missing — using stored "
                                f"portfolio_value_usd={_stored_pv:,.0f} for sizing."
                            )
                    else:
                        _live_pv = _equity_pv + _cash_raw
                        if _live_pv > 0:
                            if _stored_pv and abs(_live_pv - _stored_pv) / _stored_pv > 0.15:
                                logger.warning(
                                    f"Portfolio value drift: stored={_stored_pv:,.0f}  "
                                    f"live={_live_pv:,.0f} USD — using live for sizing."
                                )
                            _pv = _live_pv
                if _pv:
                    qp_signals = size_signals(qp_signals, _pv,
                                              risk_pct=_trade_risk_pct)

                # Inject quant signals into trend_signals so llm_advisor finds them
                trend_signals["quant_signals"] = qp_signals
                trend_signals["market_regime"]  = qp_regime

                # Inject days_to_earnings from quant features into trend_signals
                # position context for each held ticker.
                # The LLM prompt rule "dte ≤ 2 → reduce 50% (earnings pre-exit)" requires
                # this field in positions_requiring_attention — without it the rule is blind.
                # trend_signals.generate_trend_signals() only downloads price data (no earnings),
                # so dte is missing from the position context built there.
                for _t, _sig in trend_signals.get("signals", {}).items():
                    _dte = (qp_features.get(_t) or {}).get("days_to_earnings")
                    if _dte is not None:
                        _sig["days_to_earnings"] = _dte
                        # Also propagate into position sub-dict if it exists
                        if "position" in _sig:
                            _sig["position"]["days_to_earnings"] = _dte

                logger.info(f"Quant pipeline: {len(qp_signals)} signals generated")
            except Exception as qe:
                logger.error(f"Quant pipeline failed, LLM will see no quant signals: {qe}")

            save_trend_signals(trend_signals, trend_output)

            print()
            print("=" * 60)
            print("  SIGNALS GENERATED")
            print("=" * 60)
            print(f"  Tickers analyzed:     {len(trend_signals.get('universe', []))}")
            print(f"  Position contexts:    {len(trend_signals.get('signals', {}))}")
            print(f"  Quant signals (LLM):  {len(trend_signals.get('quant_signals', []))}")

            # Count breakouts and breakdowns (from position context)
            breakouts  = sum(1 for s in trend_signals.get('signals', {}).values() if s.get('breakout'))
            breakdowns = sum(1 for s in trend_signals.get('signals', {}).values() if s.get('breakdown'))
            print(f"  Breakouts detected:   {breakouts}")
            print(f"  Breakdowns detected:  {breakdowns}")
            print("=" * 60)
            print()

        except Exception as e:
            logger.error(f"Failed to generate signals: {e}")
            print()
            print("=" * 60)
            print("  SIGNALS: FAILED")
            print("=" * 60)
            print(f"  Error: {e}")
            print("=" * 60)
            print()

        # =====================================================
        # STEP 5: LLM INVESTMENT ADVISOR
        # =====================================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 5: Getting Investment Advice from LLM")
        logger.info("=" * 60)

        advice_output = f"data/investment_advice_{today}.json"

        # Run LLM if there are either trade news items OR standalone quant signals
        # (confidence ≥ 0.85 signals don't require news confirmation).
        # Previously: skip LLM when no trade news → missed breakout trades on quiet
        # news days, which are often the cleanest technical setups.
        has_quant_signals = bool(
            trend_signals and trend_signals.get("quant_signals")
        )
        if len(trade_items) == 0 and not has_quant_signals:
            logger.warning("No trade-filtered news and no quant signals. Skipping LLM advisor.")
            print()
            print("=" * 60)
            print("  LLM ADVISOR: SKIPPED")
            print("=" * 60)
            print("  Reason: No trade news and no quant signals")
            print("=" * 60)
            print()
        else:
            if len(trade_items) == 0:
                logger.info(
                    f"No trade news but {len(trend_signals.get('quant_signals', []))} "
                    "quant signal(s) present — running LLM for standalone signal evaluation"
                )
            # Auto-call the LLM API when OPENAI_API_KEY is present; otherwise save the
            # prompt to a text file for manual review (cost-controlled development mode).
            save_prompt_only = not bool(os.environ.get("OPENAI_API_KEY"))
            if save_prompt_only:
                logger.info(
                    "OPENAI_API_KEY not set — saving prompt to file. "
                    "Set OPENAI_API_KEY to enable automatic LLM advice."
                )
            result = get_investment_advice(
                trade_items, trend_signals=trend_signals, save_prompt_only=save_prompt_only
            )

            if result["success"]:
                print()
                print("=" * 60)
                print("  INVESTMENT ADVICE")
                print("=" * 60)
                print()
                print(result["advice"])
                print()
                print("=" * 60)
                if result["token_usage"]:
                    print(f"  Tokens used: {result['token_usage']['total_tokens']} "
                          f"(prompt: {result['token_usage']['prompt_tokens']}, "
                          f"completion: {result['token_usage']['completion_tokens']})")
                print("=" * 60)
                print()

                # Save advice to file
                save_advice(result["advice"], advice_output, result["token_usage"])
            else:
                logger.error(f"LLM advisor failed: {result['error']}")
                print()
                print("=" * 60)
                print("  LLM ADVISOR: FAILED")
                print("=" * 60)
                print(f"  Error: {result['error']}")
                print("=" * 60)
                print()

        # =====================================================
        # SUMMARY
        # =====================================================
        print()
        print("=" * 60)
        print("  PIPELINE COMPLETE")
        print("=" * 60)
        print(f"  Raw news:              {raw_output}")
        print(f"                         ({len(sorted_items)} items)")
        print()
        print(f"  Hygiene-filtered:      {hygiene_output}")
        print(f"                         ({len(hygiene_items)} items)")
        print()
        print(f"  Trade-filtered:        {trade_output}")
        print(f"                         ({len(trade_items)} items)")
        print()
        if trend_signals and os.path.exists(trend_output):
            print(f"  Trend signals:         {trend_output}")
            print(f"                         ({len(trend_signals.get('signals', {}))} tickers)")
            print()
        if len(trade_items) > 0 and os.path.exists(f"data/investment_advice_{today}.json"):
            print(f"  Investment advice:     data/investment_advice_{today}.json")
        print("=" * 60)
        print()

        return 0

    except Exception as e:
        logger.error(f"Fatal error in pipeline: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
