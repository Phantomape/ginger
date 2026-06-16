# exp-20260616-003 Raw SEC R&D Intensity Acceleration

Status: `rejected`
Decision: `rejected_raw_sec_rd_intensity_candidate_pool`

## Hypothesis

candidate_pool: raw SEC Companyfacts annual R&D intensity acceleration (R&D/revenue rising year over year, with R&D spend growing faster than revenue) paired with liquid SPY-relative leadership may identify innovation-investment winners whose underappreciated reinvestment shows 10-day continuation beyond price-only and static profitability sources.

## Gate 4

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1303 | -0.0325 | $117,072.92 | $117,128.88 | $+55.96 | +0.0002 | 27 | 12 |
| mid_weak | 2.1402 | 2.3078 | +0.1676 | $78,110.11 | $81,264.62 | $+3,154.51 | -0.0006 | 27 | 19 |
| old_thin | 0.5911 | 0.5587 | -0.0324 | $39,667.96 | $38,527.54 | $-1,140.42 | +0.0028 | 27 | 15 |

- Aggregate EV delta: `+0.1027`
- Aggregate PnL delta: `$+2,070.05`
- Target trades: `46`
- Accepted compression comparator: EV `+0.1608`, PnL `$+2,248.98`
- Accepted distribution comparator: EV `+0.5286`, PnL `$+10,432.91`
- Failed reasons: `window_ev_regression, window_pnl_regression, fewer_than_two_ev_improved_windows, target_concentration_failed, accepted_compression_ev_not_beaten, accepted_compression_pnl_not_beaten, accepted_distribution_ev_not_beaten, accepted_distribution_pnl_not_beaten`

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
