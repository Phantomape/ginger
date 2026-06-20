# exp-20260620-019 Raw SEC Dividend-Per-Share Increase

Status: `rejected`
Decision: `rejected_dividend_per_share_increase_candidate_pool`

## Hypothesis

candidate_pool: raw SEC Companyfacts annual common dividend per share (CommonStockDividendsPerShareDeclared) rising year over year for an established payer, with non-declining revenue and liquid SPY-relative leadership, may identify management signaling durable cash flows (Lintner / dividend-signaling) and produce next-open 10-day continuation distinct from buyback, SBC, and quality-ratio sources.

## Gate 4

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2434 | +0.0806 | $117,072.92 | $117,830.32 | $+757.40 | -0.0003 | 22 | 65 |
| mid_weak | 2.1402 | 2.2915 | +0.1513 | $78,110.11 | $81,257.63 | $+3,147.52 | -0.0014 | 22 | 61 |
| old_thin | 0.5911 | 0.4888 | -0.1023 | $39,667.96 | $35,682.65 | $-3,985.31 | +0.0056 | 22 | 61 |

- Aggregate EV delta: `+0.1296`
- Aggregate PnL delta: `$-80.39`
- Target trades: `187`
- Accepted compression comparator: EV `+0.1608`, PnL `$+2,248.98`
- Accepted distribution comparator: EV `+0.5286`, PnL `$+10,432.91`
- Failed reasons: `aggregate_pnl_not_positive, window_ev_regression, window_pnl_regression, drawdown_drift_too_high, target_concentration_failed, accepted_compression_ev_not_beaten, accepted_compression_pnl_not_beaten, accepted_distribution_ev_not_beaten, accepted_distribution_pnl_not_beaten`

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
