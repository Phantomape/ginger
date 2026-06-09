# exp-20260609-025 Form4 Liquidity Cost Cluster Purchase

Status: `rejected`
Decision: `rejected_form4_liquidity_cost_cluster_candidate_pool`

## Hypothesis

PIT-safe Form 4 meaningful purchase events should have cleaner forward value when the purchase is material versus prior 20-day dollar volume, supported by cluster or senior-owner evidence, and entered near the insiders' weighted reported purchase cost.

## Gate 4

| Window | Core EV | Raw EV | After EV | dEV Core | dEV Raw | Core PnL | Raw PnL | After PnL | dPnL Core | dPnL Raw | Qualified | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2947 | 5.1628 | +0.0000 | -0.1319 | $117,072.92 | $119,790.09 | $117,072.92 | $+0.00 | $-2,717.17 | 0 | 0 |
| mid_weak | 2.1402 | 2.2689 | 2.1649 | +0.0247 | -0.1040 | $78,110.11 | $80,173.05 | $78,724.34 | $+614.23 | $-1,448.71 | 2 | 2 |
| old_thin | 0.5911 | 0.5911 | 0.5911 | +0.0000 | +0.0000 | $39,667.96 | $39,674.07 | $39,667.96 | $+0.00 | $-6.11 | 0 | 0 |

- Aggregate EV delta vs core: `+0.0247`
- Aggregate PnL delta vs core: `$+614.23`
- Aggregate EV delta vs raw Form4: `-0.2359`
- Aggregate PnL delta vs raw Form4: `$-4,171.99`
- Selected qualified event trades: `2`
- Failed reasons: `does_not_improve_raw_form4_queue, target_sample_too_small, target_window_coverage_too_small, single_ticker_concentration, positive_pnl_hhi_concentration`

## Reflection

The stricter cluster/cost/liquidity qualifier produced too few selected trades and failed raw Form4 replacement value. The data shape shows that adding cluster or senior-owner support to the already sparse forward queue removes most events rather than creating a robust candidate-pool edge.

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
