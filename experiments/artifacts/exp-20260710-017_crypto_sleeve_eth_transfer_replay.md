# exp-20260710-017: ETH Crypto Sleeve Shared-Policy Transfer Replay

- Status: `observed_only`
- Decision: `observed_only_rejected_crypto_sleeve_eth_transfer_replay`
- Hypothesis: Observed-only alpha: the production crypto sleeve daily EMA20/EMA100/SMA200 target policy, replayed through the exact shared production policy functions over multi-year ETH-USD daily history (2017-11 to 2026 including the 2018 and 2022 bear markets), should add risk-adjusted value versus fee-aware ETH buy-and-hold if the daily trend switch generalizes across crypto assets rather than being a BTC-specific artifact.
- Runner: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260710_017_crypto_sleeve_eth_transfer_replay.py`
- Acceptance rule: positive lead iff policy EV (total_return_pct * sharpe_daily) beats fee-aware ETH buy-and-hold EV in >=2 of 3 fixed windows AND policy max drawdown < buy-and-hold max drawdown in all 3 windows AND aggregate policy total return > 0

## Windows (policy vs fee-aware buy-and-hold)

| Window | Bars | Pol ret | Pol sharpe | Pol EV | Pol maxDD | B&H ret | B&H sharpe | B&H EV | B&H maxDD | Switches | Avg pos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| eth_bear_recovery_2018_2019 | 584 | 0.374321 | 0.717067 | 0.268413 | 0.327511 | -0.776031 | -0.639241 | 0.496071 | 0.863651 | 2 | 0.176672 |
| covid_cycle_2020_2022 | 1096 | 4.629271 | 1.183102 | 5.476902 | 0.736533 | 8.058762 | 1.257055 | 10.130309 | 0.793512 | 37 | 0.548128 |
| current_cycle_2023_2026 | 1286 | -0.015983 | 0.188993 | -0.003021 | 0.637881 | 0.438456 | 0.477604 | 0.209408 | 0.676112 | 51 | 0.494241 |
| aggregate_2018_2026 | 2966 | 6.612777 | 0.74001 | 4.89352 | 0.798399 | 2.014846 | 0.58057 | 1.169759 | 0.863651 | 90 | 0.451366 |

- EV winning windows: `none`
- Drawdown winning windows: `eth_bear_recovery_2018_2019, covid_cycle_2020_2022, current_cycle_2023_2026`
- Failed reasons: `policy_ev_beats_buy_hold_in_2_of_3_windows`

## Closeout

- Production impact: Read-only historical transfer replay through the same production policy functions; the production crypto sleeve remains BTC-only and unchanged.
- Why: The unchanged production crypto sleeve trend policy did not satisfy the predeclared multi-year window rule versus fee-aware ETH buy-and-hold: policy_ev_beats_buy_hold_in_2_of_3_windows
- Forbidden retry: Do not retune EMA/SMA spans, target percentages, hysteresis, fee assumptions, window boundaries, or annualization on this same replayed ETH history to flip the verdict, and do not sweep further alt-coins one ID at a time under the same recipe; a multi-asset follow-up must be a single batched experiment.
- New evidence required: A legal follow-up is a separately predeclared default-off shared ETH sleeve policy with its own Gate 1-4 and execution envelope (if this verdict motivates one), a genuinely different crypto data source, or materially more settled production crypto sleeve forward snapshots.
