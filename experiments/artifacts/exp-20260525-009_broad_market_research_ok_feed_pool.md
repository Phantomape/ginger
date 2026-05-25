# exp-20260525-009 Broad-Market Research-Ok Feed Pool

Decision: `rejected_broad_market_research_ok_feed_pool`.

Single variable: restrict the production universe_state observation feed to research/full-history/ok-liquidity/non-sleeve records for the default-off broad-market paper sleeve.

## Candidate Pool

- tickers: `CEG, CIEN, ETN, FN, GLW, PWR, STX`
- count: `7`

## Sweep

| Variant | Gate 4 | Candidates | Trades | Changed | dEV | Rel EV | dPnL | EV Improved | EV Regressed | Max DD Worse |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_accepted_frozen_pool | FAIL | 712 | 90 | 0 | +0.0000 | +0.00% | $+0.00 | 0 | 0 | +0.0000% |
| research_ok_non_sleeve_feed_pool | FAIL | 7 | 47 | 137 | +0.0924 | +0.55% | $+1,338.01 | 1 | 2 | +0.7400% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |
|---|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.1383 | -0.2807 | $159,891.81 | $161,865.95 | $+1,974.14 |
| mid_weak | 7.3451 | 7.9433 | +0.5982 | $160,023.22 | $166,876.83 | $+6,853.61 |
| old_thin | 2.0757 | 1.8506 | -0.2251 | $94,782.99 | $87,293.25 | $-7,489.74 |

## Gate 4

```json
{
  "aggregate_ev_delta": 0.0924,
  "aggregate_pnl_delta": 1338.01,
  "candidate_ticker_count": 7,
  "changed_guard_passed": true,
  "changed_trade_count": 137,
  "changed_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "concentration_guard_passed": false,
  "drawdown_guard_passed": false,
  "identity_control_passed": true,
  "materiality_guard_passed": false,
  "max_drawdown_worse_guardrail": 0.005,
  "max_drawdown_worse_max": 0.0074,
  "max_single_ticker_positive_share": 0.5,
  "max_top5_positive_share": 0.7,
  "metrics_gate_passed": false,
  "minimum_changed_trades": 4,
  "minimum_changed_windows": 2,
  "minimum_ev_improved_windows": 3,
  "minimum_relative_ev_improvement": 0.1,
  "minimum_selected_trades": 30,
  "minimum_selected_windows": 3,
  "passed": false,
  "relative_ev_improvement": 0.005487,
  "sample_guard_passed": true,
  "selected_trade_count": 47,
  "selected_windows": 3,
  "single_ticker_positive_share": 0.373445,
  "top5_positive_share": 0.94555,
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only/default-off paper only. No shared policy, production adapter, backtester adapter, order path, core signal generation, ranking, sizing, exits, LLM, or news behavior changed.

No JavaScript was used.
