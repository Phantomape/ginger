"""
Quant Pipeline Entry Point.

Run daily to generate signals, compute risk/sizing, and produce the report.

Usage:
    cd d:/Github/ginger/quant
    python run_quant.py

Output:
    - Console: formatted daily report
    - data/report_YYYYMMDD.txt
    - data/quant_signals_YYYYMMDD.json  (full signal + feature data)
"""

import os
import json
import logging
from datetime import datetime

from earnings_snapshot import persist_earnings_snapshot

# ── Logging setup ────────────────────────────────────────────────────────────

def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s  %(levelname)-7s  %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )

# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_open_positions():
    """Load open_positions.json from data/ directory."""
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'open_positions.json'),
        'data/open_positions.json',
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    logging.getLogger(__name__).warning("open_positions.json not found")
    return None


def _save_json(obj, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


# ── Pipeline ─────────────────────────────────────────────────────────────────

def main():
    _setup_logging()
    log = logging.getLogger(__name__)

    log.info("=" * 50)
    log.info("Quant pipeline starting")
    log.info("=" * 50)

    # ── Imports (local to quant/) ────────────────────────────────────────────
    from data_layer       import get_universe, get_ohlcv, get_earnings_data
    from feature_layer    import compute_features
    from signal_engine    import generate_signals
    from risk_engine      import enrich_signals
    from portfolio_engine import size_signals, compute_portfolio_heat
    from performance_engine import compute_metrics
    from report_generator import generate_daily_report, save_report

    # ── Market regime ────────────────────────────────────────────────────────
    try:
        from regime import compute_market_regime
        log.info("Computing market regime (SPY/QQQ vs 200-day MA)...")
        market_regime = compute_market_regime()
        log.info(f"Regime: {market_regime['regime']}")
    except Exception as e:
        log.warning(f"Market regime unavailable: {e}")
        market_regime = {"regime": "UNKNOWN", "note": str(e), "indices": {}}

    # ── Step 1: Universe ─────────────────────────────────────────────────────
    universe = get_universe()
    log.info(f"Universe ({len(universe)} tickers): {universe}")

    # ── Step 2: Data Layer ───────────────────────────────────────────────────
    log.info("Downloading OHLCV data...")
    ohlcv_dict = {}
    for ticker in universe:
        ohlcv_dict[ticker] = get_ohlcv(ticker)

    log.info("Fetching earnings data...")
    earnings_dict = {}
    for ticker in universe:
        earnings_dict[ticker] = get_earnings_data(ticker)
    persist_earnings_snapshot(earnings_dict, as_of=datetime.now(), logger=log)

    # ── Step 3: Feature Layer ────────────────────────────────────────────────
    log.info("Computing features...")
    features_dict = {}
    for ticker in universe:
        features_dict[ticker] = compute_features(
            ticker, ohlcv_dict[ticker], earnings_dict[ticker]
        )

    feature_count = sum(1 for f in features_dict.values() if f is not None)
    log.info(f"Features computed for {feature_count}/{len(universe)} tickers")

    # ── Step 4: Signal Engine ────────────────────────────────────────────────
    # Build market_context in the format expected by signal_engine:
    #   "market_regime": "BULL" | "NEUTRAL" | "BEAR"
    #   "spy_10d_return": float (SPY 10-day momentum, used by RS filter)
    mc = {"market_regime": market_regime.get("regime", "")}
    spy_data = market_regime.get("indices", {}).get("SPY", {})
    if spy_data.get("momentum_10d_pct") is not None:
        mc["spy_10d_return"] = spy_data["momentum_10d_pct"]

    log.info("Generating signals...")
    signals = generate_signals(features_dict, market_context=mc)
    log.info(f"Signals: {len(signals)} triggered")

    # ── Step 5: Risk Engine ──────────────────────────────────────────────────
    signals = enrich_signals(signals, features_dict)

    # ── Step 6: Portfolio Engine ─────────────────────────────────────────────
    open_positions  = _load_open_positions()
    stored_pv       = (open_positions or {}).get("portfolio_value_usd")

    # Current prices from features (needed before portfolio value calculation)
    current_prices = {
        t: f["close"]
        for t, f in features_dict.items()
        if f and f.get("close") is not None
    }

    # Auto-compute live portfolio value from current market prices × shares.
    # portfolio_value_usd in open_positions.json is manually maintained and can be
    # stale by weeks or months.  A stale denominator inflates heat_pct by the ratio
    # (actual_value / stale_value), causing the 8% cap to trigger prematurely and
    # blocking all new trades.  Example: stored $70k, actual $150k → heat appears 2×
    # worse than reality, permanently barring new positions.
    portfolio_value = stored_pv
    if open_positions and open_positions.get("positions"):
        equity_pv = sum(
            pos.get("shares", 0) * current_prices.get(pos.get("ticker", ""), pos.get("avg_cost", 0))
            for pos in open_positions["positions"]
            if pos.get("ticker") and pos.get("shares", 0) > 0
        )
        # Include cash balance so sizing and heat reflect the full account value.
        # Without cash: a $100k account with $60k invested computes PV=$60k →
        # positions sized for 0.6% risk (not 1%) and heat appears 1.67× inflated.
        # Add cash_usd field to open_positions.json to enable correct calculation.
        cash_raw = open_positions.get("cash_usd")
        if cash_raw is None:
            if stored_pv:
                log.warning(
                    f"⚠️  cash_usd missing in open_positions.json — using stored "
                    f"portfolio_value_usd={stored_pv:,.0f} USD for heat and sizing. "
                    f"Fill cash_usd to enable live PV."
                )
        else:
            live_pv = equity_pv + cash_raw
            if live_pv > 0:
                if stored_pv and abs(live_pv - stored_pv) / stored_pv > 0.15:
                    log.warning(
                        f"⚠️  Portfolio value drift detected: stored={stored_pv:,.0f} USD  "
                        f"live={live_pv:,.0f} USD  (equity={equity_pv:,.0f} + cash={cash_raw:,.0f}).  "
                        f"Using live value for heat and sizing calculations. "
                        f"Update portfolio_value_usd in open_positions.json to suppress this warning."
                    )
                portfolio_value = live_pv
                log.info(f"Portfolio value: live={live_pv:,.0f} USD (stored={stored_pv or 'N/A'})")
            elif stored_pv:
                # Fallback: positions have no current price data (e.g. yfinance failure)
                log.warning(
                    f"Could not compute live portfolio value (no current prices for positions). "
                    f"Falling back to stored value: {stored_pv:,.0f} USD."
                )
    elif stored_pv:
        # Stale portfolio data warning
        if open_positions and open_positions.get("as_of"):
            try:
                as_of_dt   = datetime.strptime(open_positions["as_of"], "%Y-%m-%d")
                days_stale = (datetime.now() - as_of_dt).days
                if days_stale > 30:
                    log.warning(
                        f"⚠️  open_positions.json is {days_stale} days stale "
                        f"(as_of={open_positions['as_of']}). "
                        f"Update portfolio_value_usd to current account value."
                    )
            except Exception:
                pass

    portfolio_heat = None
    if open_positions and portfolio_value:
        # Pass features_dict so effective stops (ATR/trailing) are used for
        # large winners — without it, heat falls back to hard_stop only and
        # overstates at-risk USD for positions with >100% unrealised gains.
        portfolio_heat = compute_portfolio_heat(
            open_positions, current_prices, portfolio_value,
            features_dict=features_dict,
        )
        log.info(portfolio_heat["heat_note"])
    else:
        log.warning("Set portfolio_value_usd in open_positions.json to enable heat tracking")

    # Add position sizing to signals
    if portfolio_value:
        signals = size_signals(signals, portfolio_value)

    # ── Step 7: Performance Engine ───────────────────────────────────────────
    metrics = compute_metrics(portfolio_value=portfolio_value)
    if metrics.get("total_trades", 0) > 0:
        log.info(
            f"P&L  trades={metrics['total_trades']}  "
            f"WR={metrics['win_rate']*100:.0f}%  "
            f"EV=${metrics['expected_value_usd']:,.2f}  "
            f"total=${metrics['total_pnl_usd']:,.2f}"
        )
    else:
        log.info(metrics.get("note", "No closed trades yet"))

    # ── Step 8: Report ───────────────────────────────────────────────────────
    report = generate_daily_report(
        signals        = signals,
        features_dict  = features_dict,
        portfolio_heat = portfolio_heat,
        metrics        = metrics,
        market_regime  = market_regime,
        open_positions = open_positions,
    )

    print("\n" + report)

    report_path = save_report(report)
    if report_path:
        log.info(f"Report → {report_path}")

    # ── Save full signals JSON ───────────────────────────────────────────────
    today        = datetime.now().strftime("%Y%m%d")
    signals_path = os.path.join(
        os.path.dirname(__file__), '..', 'data', f'quant_signals_{today}.json'
    )
    _save_json({
        "generated_at":   datetime.now().isoformat(),
        "market_regime":  market_regime,
        "portfolio_heat": portfolio_heat,
        "signals":        signals,
        "features":       features_dict,
    }, signals_path)
    log.info(f"Signals JSON → {signals_path}")

    log.info("Quant pipeline complete.")
    return signals


if __name__ == "__main__":
    main()
