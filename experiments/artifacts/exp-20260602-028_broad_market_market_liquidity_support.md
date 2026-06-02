# exp-20260602-028 Broad-Market Market-Liquidity Support

Decision: `rejected_broad_market_market_liquidity_support`.

Single causal variable: default-off paper-notional support for already-selected
broad-market paper entries when SPY/QQQ/IWM show adequate 20d/60d
liquidity participation and orderly 20d/current range.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | PnL Regressed | Max DD Worse |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_market_liquidity_support | FAIL | 0 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% |
| minliq0p90_range20lte0p022_currlte0p030_scalar1p05 | FAIL | 51 | +0.0596 | $+1,503.20 | 2 | 1 | 0 | +0.0200% |
| minliq1p00_range20lte0p022_currlte0p030_scalar1p05 | FAIL | 33 | +0.0241 | $+930.46 | 2 | 1 | 0 | +0.0000% |
| minliq0p90_range20lte0p026_currlte0p035_scalar1p05 | FAIL | 58 | +0.0561 | $+1,423.97 | 2 | 1 | 0 | +0.0200% |
| minliq1p00_range20lte0p026_currlte0p035_scalar1p05 | FAIL | 40 | +0.0204 | $+851.22 | 2 | 1 | 0 | +0.0000% |
| minliq0p90_range20lte0p030_currlte0p040_scalar1p05 | FAIL | 61 | +0.0558 | $+1,408.17 | 2 | 1 | 1 | +0.0200% |
| minliq1p00_range20lte0p030_currlte0p040_scalar1p05 | FAIL | 40 | +0.0204 | $+851.22 | 2 | 1 | 0 | +0.0000% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted Trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4494 | +0.0304 | $159,891.81 | $160,547.77 | $+655.96 | 17 |
| mid_weak | 7.3451 | 7.3836 | +0.0385 | $160,023.22 | $160,863.46 | $+840.24 | 18 |
| old_thin | 2.0757 | 2.0664 | -0.0093 | $94,782.99 | $94,789.99 | $+7.00 | 16 |

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
  "promotion_blocker": "If positive, implement the same market-liquidity regime through a shared default-off broad-market paper helper before retention. This run does not create production/backtest behavior divergence because it does not promote the support scalar.",
  "replay_only": true,
  "research_replay_alters_paper_notional": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
