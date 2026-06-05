# exp-20260605-003: SEC FTD + Companyfacts Gross-Margin Candidate Pool

- decision: `rejected_sec_ftd_companyfacts_gross_margin_candidate_pool`
- aggregate EV: `7.8941` -> `7.94` (+0.0459)
- aggregate PnL delta: `$+517.02`
- target trades: `11`
- accepted FTD+FINRA after EV delta: `-0.3961`
- accepted FTD+FINRA after PnL delta: `$-9583.47`
- max single positive share: `0.746007`
- positive PnL HHI: `0.621039`
- failed gates: `accepted_ftd_finra_aggregate_ev_not_beaten, accepted_ftd_finra_aggregate_pnl_not_beaten, accepted_ftd_finra_window_ev_regression, accepted_ftd_finra_window_pnl_regression, target_concentration_failed, target_sample_too_small, window_ev_regression, window_pnl_regression`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1886 | +0.0258 | $+315.22 | 1 |
| mid_weak | 2.1402 | 2.1760 | +0.0358 | $+731.60 | 5 |
| old_thin | 0.5911 | 0.5754 | -0.0157 | $-529.80 | 5 |

## Accepted FTD+FINRA Comparator

| window | ours after EV | accepted after EV | EV delta | ours after PnL | accepted after PnL | PnL delta |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1886 | 5.3853 | -0.1967 | $117,388.14 | $119,940.25 | $-2,552.11 |
| mid_weak | 2.1760 | 2.1884 | -0.0124 | $78,841.71 | $80,162.83 | $-1,321.12 |
| old_thin | 0.5754 | 0.7624 | -0.1870 | $39,138.16 | $44,848.40 | $-5,710.24 |

## Conclusion

Gate 4 or the accepted FTD+FINRA comparator failed; no production or shared policy behavior is retained.

The tested fields are SEC FTD rows after conservative publication lag, SEC Companyfacts rows after filed-date visibility, and same-day/prior OHLCV. The result is replay-only/default-off: no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| CIFR | 4 | $925.84 | 0.746007 |
| WULF | 1 | $315.22 | 0.253993 |
| CRDO | 3 | $-528.26 | None |
| GOOG | 1 | $-180.83 | None |
| SNOW | 2 | $-14.95 | None |
