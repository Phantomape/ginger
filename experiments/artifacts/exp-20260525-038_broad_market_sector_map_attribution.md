# exp-20260525-038 Broad-Market Sector Map Attribution

Decision: `accepted_broad_market_sector_map_attribution`.

Read-only `measurement_repair`. Builds and validates the
`yfinance_gics_proxy_sector_v1` sector cache for the broad-market
warehouse universe and attaches sector context to the accepted
`exp-20260520-004` baseline replay. Unlocks broad-market
sector-aware alpha_search; does not change orders or notional.

## Gate 1 Core Replay Verification

```json
{
  "baseline_artifact": "data/experiments/exp-20260517-009/ample_slot_stock_rank1_topup.json",
  "baseline_protocol": "docs/backtesting.md canonical three fixed windows",
  "by_window": {
    "late_strong": {
      "expected_value_score": 5.1628,
      "max_drawdown_pct": 0.0665,
      "sharpe_daily": 4.41,
      "signals_generated": 51,
      "signals_survived": 41,
      "survival_rate": 0.8039,
      "total_pnl": 117072.92,
      "total_return_pct": 1.1707,
      "trade_count": 18,
      "win_rate": 0.8333
    },
    "mid_weak": {
      "expected_value_score": 2.1402,
      "max_drawdown_pct": 0.1119,
      "sharpe_daily": 2.74,
      "signals_generated": 53,
      "signals_survived": 42,
      "survival_rate": 0.7925,
      "total_pnl": 78110.11,
      "total_return_pct": 0.7811,
      "trade_count": 21,
      "win_rate": 0.5238
    },
    "old_thin": {
      "expected_value_score": 0.5911,
      "max_drawdown_pct": 0.1001,
      "sharpe_daily": 1.49,
      "signals_generated": 60,
      "signals_survived": 52,
      "survival_rate": 0.8667,
      "total_pnl": 39667.96,
      "total_return_pct": 0.3967,
      "trade_count": 22,
      "win_rate": 0.4091
    }
  },
  "canonical_accepted_aggregate_expected_value_score_sum": 7.8941,
  "canonical_accepted_aggregate_total_pnl_sum": 234850.99,
  "ev_tolerance": 0.01,
  "expected_value_score_drift": 0.0,
  "observed_aggregate_expected_value_score_sum": 7.8941,
  "observed_aggregate_total_pnl_sum": 234850.99,
  "passed": true,
  "pnl_tolerance": 50.0,
  "total_pnl_drift": 0.0
}
```

## Sector Coverage on Warehouse Universe

```json
{
  "cache_generated_at": "2026-05-27T05:25:19Z",
  "coverage_target": 0.8,
  "coverage_target_passed": true,
  "ok_share": 0.998596,
  "rule_version": "yfinance_gics_proxy_sector_v1",
  "scope": "frozen_candidate_universe_from_source_artifact",
  "sector_counts": {
    "Basic Materials": 39,
    "Communication Services": 25,
    "Consumer Cyclical": 91,
    "Consumer Defensive": 34,
    "Energy": 47,
    "Financial Services": 110,
    "Healthcare": 85,
    "Industrials": 112,
    "Real Estate": 33,
    "Technology": 109,
    "Utilities": 26
  },
  "sector_unique_count": 11,
  "source": "yfinance.Ticker.info.sector",
  "status_counts": {
    "fetch_error": 1,
    "missing_info": 0,
    "missing_ticker": 0,
    "ok": 711
  },
  "status_shares": {
    "fetch_error": 0.001404,
    "missing_info": 0.0,
    "missing_ticker": 0.0,
    "ok": 0.998596
  },
  "tickers_requested": 712,
  "tickers_unique": 712,
  "unresolved_sample": [
    "FNGD"
  ],
  "warehouse_diagnostic": {
    "cache_generated_at": "2026-05-27T05:25:19Z",
    "ok_share": 0.884644,
    "rule_version": "yfinance_gics_proxy_sector_v1",
    "sector_counts": {
      "Basic Materials": 66,
      "Communication Services": 41,
      "Consumer Cyclical": 158,
      "Consumer Defensive": 61,
      "Energy": 78,
      "Financial Services": 168,
      "Healthcare": 137,
      "Industrials": 182,
      "Real Estate": 53,
      "Technology": 195,
      "Utilities": 42
    },
    "sector_unique_count": 11,
    "source": "yfinance.Ticker.info.sector",
    "status_counts": {
      "fetch_error": 154,
      "missing_info": 0,
      "missing_ticker": 0,
      "ok": 1181
    },
    "status_shares": {
      "fetch_error": 0.115356,
      "missing_info": 0.0,
      "missing_ticker": 0.0,
      "ok": 0.884644
    },
    "tickers_requested": 1335,
    "tickers_unique": 1335,
    "unresolved_sample": [
      "FNGD",
      "GDXU",
      "SPGI",
      "SYM",
      "TECH",
      "TEL",
      "TGTX",
      "THC",
      "THG",
      "TPL",
      "TRNO",
      "TXNM",
      "VALE",
      "VIK",
      "VLY",
      "VTR",
      "WHR",
      "WK",
      "WMG",
      "WRB",
      "WTW",
      "WY",
      "YETI",
      "ZBH",
      "ZETA"
    ]
  }
}
```

## Aggregate Sector Attribution Across 3 Windows

| Sector | Trades | PnL |
|---|---:|---:|
| Industrials | 19 | $11,441.83 |
| Technology | 16 | $17,472.83 |
| Consumer Cyclical | 15 | $3,727.23 |
| Healthcare | 13 | $-3,559.21 |
| Communication Services | 8 | $914.48 |
| Basic Materials | 6 | $6,286.27 |
| Consumer Defensive | 4 | $-343.13 |
| Financial Services | 4 | $-3,095.03 |
| Energy | 3 | $-3,434.41 |
| Utilities | 1 | $-129.34 |
| Real Estate | 1 | $-305.98 |

## Gate 4

```json
{
  "broad_market_pnl_parity_drift": {
    "late_strong": 0.0,
    "mid_weak": 0.0,
    "old_thin": 0.0
  },
  "broad_market_pnl_parity_passed": true,
  "canonical_backtest_required": true,
  "gate1_passed": true,
  "note": "Measurement repair: Gate 4 requires core parity, broad-market PnL parity vs the accepted source artifact, and coverage >= 80% on the warehouse universe.",
  "passed": true,
  "sector_coverage_observed": 0.998596,
  "sector_coverage_passed": true,
  "sector_coverage_target": 0.8,
  "strategy_behavior_changed": false
}
```

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "parity_test_added": true,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false,
  "trade_enabled": false
}
```

No JavaScript was used.
