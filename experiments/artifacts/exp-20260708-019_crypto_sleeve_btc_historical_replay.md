# exp-20260708-019: BTC Crypto Sleeve Shared-Policy Historical Replay

- Status: `observed_only`
- Decision: `observed_only_positive_lead_crypto_sleeve_historical_replay`
- Hypothesis: Observed-only alpha: the production BTC/USD crypto sleeve daily EMA20/EMA100/SMA200 target policy, replayed through the exact shared production policy functions over multi-year BTC-USD daily history (2017-2026 including the 2018 and 2022 bear markets), should add risk-adjusted value versus fee-aware BTC buy-and-hold if the daily trend switch is a real edge rather than a short-sample artifact.
- Runner: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260708_019_crypto_sleeve_btc_historical_replay.py`
- Acceptance rule: positive lead iff policy EV (total_return_pct * sharpe_daily) beats fee-aware buy-and-hold EV in >=2 of 3 fixed windows AND policy max drawdown < buy-and-hold max drawdown in all 3 windows AND aggregate policy total return > 0

## Windows (policy vs fee-aware buy-and-hold)

| Window | Bars | Pol ret | Pol sharpe | Pol EV | Pol maxDD | B&H ret | B&H sharpe | B&H EV | B&H maxDD | Switches | Avg pos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bull_bear_2017_2019 | 1095 | 9.474328 | 1.529171 | 14.48787 | 0.531103 | 6.135546 | 1.204211 | 7.388494 | 0.83399 | 24 | 0.503199 |
| covid_cycle_2020_2022 | 1096 | 2.185535 | 1.077 | 2.353822 | 0.407734 | 1.275359 | 0.750537 | 0.957204 | 0.766346 | 39 | 0.471142 |
| current_cycle_2023_2026 | 1284 | 1.30201 | 0.848791 | 1.105134 | 0.327024 | 2.769989 | 1.036156 | 2.870141 | 0.5306 | 43 | 0.598909 |
| aggregate_2017_2026 | 3475 | 75.80967 | 1.169372 | 88.649733 | 0.531103 | 61.787442 | 0.981904 | 60.669309 | 0.83399 | 106 | 0.528152 |

- EV winning windows: `bull_bear_2017_2019, covid_cycle_2020_2022`
- Drawdown winning windows: `bull_bear_2017_2019, covid_cycle_2020_2022, current_cycle_2023_2026`
- Failed reasons: `none`

## Closeout

- Production impact: Read-only historical replay through the same production policy functions; the production crypto sleeve remains as-is.
- Why: The unchanged production crypto sleeve trend policy beat fee-aware BTC buy-and-hold on the predeclared risk-adjusted window rule over multi-year history; this validates keeping the current sleeve policy but changes nothing by itself.
- Forbidden retry: Do not retune EMA/SMA spans, target percentages, hysteresis, fee assumptions, window boundaries, or annualization on this same replayed BTC history to flip the verdict.
- New evidence required: A legal follow-up is either a separately predeclared shared policy change with its own Gate 1-4 replay (if the verdict motivates one), a different crypto data source or asset, or materially more settled production crypto sleeve forward snapshots.
