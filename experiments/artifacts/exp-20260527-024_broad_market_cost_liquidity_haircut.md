# exp-20260527-024 Broad-Market Cost/Liquidity Haircut

Decision: `rejected_broad_market_cost_liquidity_haircut`.

Single causal variable: paper-notional haircut for accepted broad-market
paper entries whose decision-date OHLCV cost/liquidity proxy is high.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | PnL Regressed | Max DD Worse |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_cost_liquidity_haircut | FAIL | 0 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% |
| high_expected_cost_scalar_0p90 | FAIL | 39 | -0.0524 | $-1,625.29 | 0 | 3 | 3 | +0.0600% |
| high_expected_cost_scalar_0p80 | FAIL | 39 | -0.0891 | $-3,250.54 | 0 | 3 | 3 | +0.1100% |
| high_expected_cost_scalar_0p65 | FAIL | 39 | -0.1759 | $-5,688.42 | 0 | 3 | 3 | +0.1900% |
| high_expected_cost_scalar_0p50 | FAIL | 39 | -0.2788 | $-8,126.34 | 0 | 3 | 3 | +0.2700% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted Trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.3904 | -0.0286 | $159,891.81 | $158,933.24 | $-958.57 | 14 |
| mid_weak | 7.3451 | 7.3275 | -0.0176 | $160,023.22 | $159,639.56 | $-383.66 | 13 |
| old_thin | 2.0757 | 2.0695 | -0.0062 | $94,782.99 | $94,499.93 | $-283.06 | 12 |

## Baseline Replay Parity

```json
{
  "passed": true,
  "pnl_drift": {
    "late_strong": 0.0,
    "mid_weak": 0.0,
    "old_thin": 0.0
  },
  "replayed_pnl_by_window": {
    "late_strong": 10307.76,
    "mid_weak": 14607.88,
    "old_thin": 4059.9
  },
  "replayed_trade_count_by_window": {
    "late_strong": 30,
    "mid_weak": 30,
    "old_thin": 30
  },
  "source_experiment_id": "exp-20260520-004",
  "source_pnl_by_window": {
    "late_strong": 10307.76,
    "mid_weak": 14607.88,
    "old_thin": 4059.9
  },
  "source_trade_count_by_window": {
    "late_strong": 30,
    "mid_weak": 30,
    "old_thin": 30
  },
  "trade_count_drift": {
    "late_strong": 0,
    "mid_weak": 0,
    "old_thin": 0
  }
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "production_signal_path_changed": false,
  "promotion_blocker": "If positive, implement the same cost/liquidity proxy through a shared default-off broad-market paper adapter before retention. This run does not create production/backtest behavior divergence because it does not promote the haircut.",
  "replay_only": true,
  "research_replay_alters_paper_notional": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
