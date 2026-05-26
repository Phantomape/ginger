# exp-20260526-016 Theme-Density Confirmed Breakout Paper Sleeve

Decision: `rejected_theme_density_breakout_sleeve`.

Single variable: a default-off paper sleeve admits at most one liquid breakout candidate per day only when same-theme participation and SPY-relative theme strength confirm the setup.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates | Theme days | Tickers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9035 | -0.2593 | $117,072.92 | $114,299.59 | $-2,773.33 | +0.0001 | 7 | 21 | 17 | 11 |
| mid_weak | 1.5576 | 2.1687 | +0.6111 | $64,898.46 | $78,014.44 | $+13,115.98 | -0.0036 | 28 | 60 | 41 | 12 |
| old_thin | 0.5911 | 0.5839 | -0.0072 | $39,667.96 | $39,450.36 | $-217.60 | +0.0001 | 14 | 25 | 21 | 11 |

## Aggregate

- EV delta: `0.3446` (`0.047131`)
- PnL delta: `$10125.05` (`0.045683`)
- target trades: `49` across `3` windows
- max single positive share: `0.426588`
- positive PnL HHI: `0.267212`

## Theme-Density Audit

```json
{
  "late_strong": {
    "candidate_days": 13,
    "candidate_source_tickers": 38,
    "raw_liquid_theme_density_breakout_hits": 21,
    "rule_version": "theme_density_confirmed_breakout_v1",
    "selected_theme_counts": {
      "ai": 13,
      "mega_cap": 8
    },
    "theme_groups": {
      "ai": [
        "AMD",
        "AVGO",
        "CRDO",
        "MU",
        "NVDA",
        "TSM"
      ],
      "crypto": [
        "COIN"
      ],
      "mega_cap": [
        "AAPL",
        "AMZN",
        "GOOG",
        "META",
        "MSFT",
        "NVDA",
        "TSLA"
      ]
    },
    "theme_pass_counts": {
      "ai": 16,
      "mega_cap": 8
    },
    "theme_pass_days": 17,
    "theme_pass_instances": 145,
    "trading_days": 123,
    "unique_candidate_tickers": 11
  },
  "mid_weak": {
    "candidate_days": 28,
    "candidate_source_tickers": 38,
    "raw_liquid_theme_density_breakout_hits": 60,
    "rule_version": "theme_density_confirmed_breakout_v1",
    "selected_theme_counts": {
      "ai": 47,
      "mega_cap": 13
    },
    "theme_groups": {
      "ai": [
        "AMD",
        "AVGO",
        "CRDO",
        "MU",
        "NVDA",
        "TSM"
      ],
      "crypto": [
        "COIN"
      ],
      "mega_cap": [
        "AAPL",
        "AMZN",
        "GOOG",
        "META",
        "MSFT",
        "NVDA",
        "TSLA"
      ]
    },
    "theme_pass_counts": {
      "ai": 33,
      "mega_cap": 19
    },
    "theme_pass_days": 41,
    "theme_pass_instances": 320,
    "trading_days": 127,
    "unique_candidate_tickers": 12
  },
  "old_thin": {
    "candidate_days": 14,
    "candidate_source_tickers": 38,
    "raw_liquid_theme_density_breakout_hits": 25,
    "rule_version": "theme_density_confirmed_breakout_v1",
    "selected_theme_counts": {
      "ai": 10,
      "mega_cap": 15
    },
    "theme_groups": {
      "ai": [
        "AMD",
        "AVGO",
        "CRDO",
        "MU",
        "NVDA",
        "TSM"
      ],
      "crypto": [
        "COIN"
      ],
      "mega_cap": [
        "AAPL",
        "AMZN",
        "GOOG",
        "META",
        "MSFT",
        "NVDA",
        "TSLA"
      ]
    },
    "theme_pass_counts": {
      "ai": 11,
      "mega_cap": 13
    },
    "theme_pass_days": 21,
    "theme_pass_instances": 154,
    "trading_days": 138,
    "unique_candidate_tickers": 11
  }
}
```

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.426588,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.267212,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 49,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
