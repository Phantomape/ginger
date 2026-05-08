# exp-20260508-010 SMA20 Reclaim Missed Sleeve Audit

## Decision

- decision: rejected
- missed candidate count: 8
- fixed-notional PnL: -1710.86
- win rate: 0.375
- positive windows: 1
- single ticker positive share: 0.5707
- gate failures: total_pnl_not_positive, win_rate_lt_50pct, single_ticker_positive_share_gt_50pct, positive_windows_lt_2

## Canonical Baseline

- late_strong: EV=3.7435, sharpe_daily=4.48, pnl=83562.53, max_dd=0.0539, win_rate=0.79, trades=19
- mid_weak: EV=1.5478, sharpe_daily=2.69, pnl=57542.74, max_dd=0.0879, win_rate=0.524, trades=21
- old_thin: EV=0.3359, sharpe_daily=1.28, pnl=26242.68, max_dd=0.0905, win_rate=0.409, trades=22

## By Window

- late_strong: count=2, pnl=-2040.69, win_rate=0.0, tickers={'DDOG': -1838.97, 'V': -201.72}
- mid_weak: count=3, pnl=365.22, win_rate=0.6667, tickers={'AAPL': -34.0, 'MCD': 233.76, 'RTX': 165.46}
- old_thin: count=3, pnl=-35.39, win_rate=0.3333, tickers={'CAT': -536.18, 'CVX': 530.73, 'JPM': -29.94}

## Notes

- Observed-only fixed-notional sleeve audit.
- Does not change production signals, sizing, orders, ranking, exits, prompts, or core slots.
- Broad pullback/reclaim variants remain rejected; this result only applies to existing A/B missed candidate rows.
