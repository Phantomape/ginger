# exp-20260604-023: SEC FTD Pressure Breakout Candidate Pool

- decision: `rejected_sec_ftd_pressure_breakout_candidate_pool`
- aggregate EV: `7.8941` -> `8.3743` (+0.4802)
- aggregate PnL delta: `$+7,754.98`
- target trades: `270`
- max single positive share: `0.128121`
- positive PnL HHI: `0.044115`
- SEC FTD rows loaded: `220288`
- failed gates: `window_ev_regression, window_pnl_regression`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1313 | -0.0315 | $-453.62 | 78 |
| mid_weak | 2.1402 | 2.5266 | +0.3864 | $+4,457.76 | 102 |
| old_thin | 0.5911 | 0.7164 | +0.1253 | $+3,750.84 | 90 |

## Conclusion

Gate 4 failed; no production or shared policy behavior is retained.

The rule uses only SEC FTD rows after the conservative publication-lag date plus same-day/prior OHLCV context. It is replay-only and default-off, so no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| IONQ | 6 | $5,055.30 | 0.128121 |
| OKLO | 3 | $3,796.50 | 0.096218 |
| SOUN | 2 | $2,910.08 | 0.073753 |
| WIX | 4 | $2,021.10 | 0.051223 |
| YPF | 4 | $1,412.01 | 0.035786 |
| CLSK | 2 | $1,402.88 | 0.035555 |
| UUUU | 1 | $1,062.57 | 0.02693 |
| KNX | 3 | $1,043.65 | 0.02645 |
| CDE | 1 | $891.88 | 0.022604 |
| ACMR | 1 | $828.14 | 0.020988 |
