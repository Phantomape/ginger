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
    log.info("Generating signals...")
    signals = generate_signals(features_dict)
    log.info(f"Signals: {len(signals)} triggered")

    # ── Step 5: Risk Engine ──────────────────────────────────────────────────
    signals = enrich_signals(signals, features_dict)

    # ── Step 6: Portfolio Engine ─────────────────────────────────────────────
    open_positions  = _load_open_positions()
    portfolio_value = (open_positions or {}).get("portfolio_value_usd")

    # Current prices from features
    current_prices = {
        t: f["close"]
        for t, f in features_dict.items()
        if f and f.get("close") is not None
    }

    portfolio_heat = None
    if open_positions and portfolio_value:
        portfolio_heat = compute_portfolio_heat(open_positions, current_prices, portfolio_value)
        log.info(portfolio_heat["heat_note"])
    else:
        log.warning("Set portfolio_value_usd in open_positions.json to enable heat tracking")

    # Add position sizing to signals
    if portfolio_value:
        signals = size_signals(signals, portfolio_value)

    # ── Step 7: Performance Engine ───────────────────────────────────────────
    metrics = compute_metrics()
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
