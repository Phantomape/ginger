# exp-20260608-011: Revision Surprise Low-Extension Tail-State Candidate Pool

- decision: `positive_proxy_lead_not_promoted_revision_surprise_low_extension`
- aggregate EV: `7.8941` -> `8.0787` (+0.1846)
- aggregate PnL delta: `$+2,893.75`
- target trades: `31`
- max single positive share: `0.415681`
- positive PnL HHI: `0.244677`
- failed gates: `none`
- numeric Gate 4 passed: `True`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3088 | +0.1460 | $+1,425.44 | 7 |
| mid_weak | 2.1402 | 2.1591 | +0.0189 | $+689.36 | 15 |
| old_thin | 0.5911 | 0.6108 | +0.0197 | $+778.95 | 9 |

## Conclusion

Numeric Gate 4 passed, but this remains a replay-only proxy lead: the historical EPS-estimate and surprise-history source still requires a shared PIT analyst-revision adapter with production/backtest parity before promotion.

The tested fields are daily earnings-snapshot EPS estimates, same-day/prior OHLCV, and SPY relative strength. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| MU | 3 | $1,493.15 | 0.415681 |
| DDOG | 2 | $647.12 | 0.180153 |
| LLY | 2 | $606.53 | 0.168853 |
| GE | 1 | $275.76 | 0.076769 |
| NFLX | 1 | $154.62 | 0.043045 |
| BKNG | 1 | $146.70 | 0.04084 |
| DIS | 2 | $91.57 | 0.025492 |
| JPM | 1 | $85.56 | 0.023819 |
| MA | 2 | $46.21 | 0.012864 |
| AAPL | 2 | $39.47 | 0.010988 |

## Low-Extension Tail Gate

- max ret20_excess_spy: `0.35`
- selection policy: `selected_top1_gate_no_backup_substitution`
- production parity: replay-only; no production/default path changed.
