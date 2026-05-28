# exp-20260528-008 Operating-Profit Closed-Ledger Governor

Decision: `accepted_candidate_operating_profit_quality_closed_ledger_governor`.

Single variable: apply a production-visible closed-paper-ledger governor to the exp-20260528-004 operating-profit quality sleeve.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Profit-cap scaled | DD scaled |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 7.3793 | +2.2165 | $117,072.92 | $139,758.70 | $+22,685.78 | -0.0086 | 99 | 34 | 0 |
| mid_weak | 2.1402 | 5.5164 | +3.3762 | $78,110.11 | $127,402.51 | $+49,292.40 | -0.0204 | 116 | 31 | 0 |
| old_thin | 0.5911 | 2.3293 | +1.7382 | $39,667.96 | $78,958.71 | $+39,290.75 | -0.0048 | 121 | 53 | 19 |

## Aggregate

- EV delta: `7.3309` (`0.928656`)
- PnL delta: `$111268.93` (`0.473785`)
- target trades: `336`
- max drawdown drift: `-0.0048`
- max single positive share: `0.391352`
- positive PnL HHI: `0.249167`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_checks": [],
  "max_drawdown_worse": -0.0048,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.391352,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.249167,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 336,
  "target_trade_count_min": 30,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Governor Audit

```json
{
  "late_strong": {
    "daily_top1_filtered": 127,
    "filtered_candidates": 161,
    "final_closed_pnl": 22685.78,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "input_candidates": 260,
    "max_closed_drawdown_seen_usd": 6367.12,
    "missing_trade_filtered": 31,
    "rule_version": "operating_profit_quality_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 3,
    "scaled_ticker_counts": {
      "MU": 34
    },
    "selected_ticker_counts": {
      "AMD": 4,
      "APP": 5,
      "CRDO": 4,
      "GOOG": 14,
      "MU": 63,
      "RTX": 9
    },
    "selected_trades": 99,
    "selected_unique_tickers": 6,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 34
  },
  "mid_weak": {
    "daily_top1_filtered": 268,
    "filtered_candidates": 283,
    "final_closed_pnl": 49292.4,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "input_candidates": 399,
    "max_closed_drawdown_seen_usd": 4293.7,
    "missing_trade_filtered": 11,
    "rule_version": "operating_profit_quality_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 4,
    "scaled_ticker_counts": {
      "APP": 6,
      "CRDO": 21,
      "PLTR": 4
    },
    "selected_ticker_counts": {
      "AMD": 11,
      "APP": 18,
      "AVGO": 3,
      "COIN": 11,
      "CRDO": 30,
      "MU": 15,
      "NFLX": 2,
      "NVDA": 1,
      "PLTR": 25
    },
    "selected_trades": 116,
    "selected_unique_tickers": 9,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 31
  },
  "old_thin": {
    "both_scalars_applied": 3,
    "daily_top1_filtered": 221,
    "filtered_candidates": 238,
    "final_closed_pnl": 39290.75,
    "global_closed_drawdown_trigger_usd": 7500.0,
    "global_drawdown_scalar": 0.25,
    "global_drawdown_scaled": 19,
    "input_candidates": 359,
    "max_closed_drawdown_seen_usd": 11440.2,
    "missing_trade_filtered": 12,
    "rule_version": "operating_profit_quality_closed_ledger_governor_v1",
    "same_ticker_core_overlap_filtered": 5,
    "scaled_ticker_counts": {
      "APP": 33,
      "PLTR": 20
    },
    "selected_ticker_counts": {
      "APP": 50,
      "AVGO": 13,
      "COIN": 1,
      "ISRG": 2,
      "META": 3,
      "MU": 1,
      "NFLX": 7,
      "NOW": 3,
      "PLTR": 27,
      "RTX": 14
    },
    "selected_trades": 121,
    "selected_unique_tickers": 10,
    "ticker_closed_profit_cap_usd": 9000.0,
    "ticker_profit_cap_scalar": 0.05,
    "ticker_profit_cap_scaled": 53
  }
}
```

## Production Impact

Experiment-only default-off paper evidence. No shared policy, run adapter, backtester adapter, production watchlist, live/default order path, core entry, ranking, sizing, or exit behavior changed. A production promotion would need this exact closed-ledger state and governor in a shared adapter plus parity tests.

No JavaScript was used.
