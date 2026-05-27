# exp-20260527-901 Broad-Market Sector Open-Crowding Haircut

Decision: `rejected_broad_market_sector_open_crowding_haircut`.

Single causal variable: paper-notional haircut for accepted broad-market
paper entries when the same sector is already active in the sleeve.

## Sweep

| Variant | Gate 4 | Adjusted | dEV | dPnL | EV Improved | EV Regressed | PnL Regressed | Max DD Worse |
|---|:---:|---:|---:|---:|---:|---:|---:|---:|
| baseline_no_sector_open_crowding_haircut | FAIL | 0 | +0.0000 | $+0.00 | 0 | 0 | 0 | +0.0000% |
| same_sector_active_gte_1_scalar_0p90 | FAIL | 42 | -0.0108 | $-650.02 | 1 | 2 | 3 | +0.0000% |
| same_sector_active_gte_1_scalar_0p80 | FAIL | 42 | -0.0058 | $-1,299.98 | 1 | 2 | 3 | +0.0100% |
| same_sector_active_gte_1_scalar_0p65 | FAIL | 42 | -0.0209 | $-2,274.97 | 1 | 2 | 3 | +0.0100% |
| same_sector_active_gte_1_scalar_0p50 | FAIL | 42 | -0.0295 | $-3,249.99 | 1 | 2 | 3 | +0.0200% |

## Three-Window Evidence

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Adjusted Trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 7.4190 | 7.4400 | +0.0210 | $159,891.81 | $159,656.45 | $-235.36 | 13 |
| mid_weak | 7.3451 | 7.3238 | -0.0213 | $160,023.22 | $159,213.51 | $-809.71 | 15 |
| old_thin | 2.0757 | 2.0702 | -0.0055 | $94,782.99 | $94,528.08 | $-254.91 | 14 |

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
  "promotion_blocker": "If positive, implement through shared broad_market_paper_sleeve state-aware default-off adapter before retention; this run does not create production/backtest behavior divergence because it does not promote the haircut.",
  "replay_only": true,
  "research_replay_alters_paper_notional": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
