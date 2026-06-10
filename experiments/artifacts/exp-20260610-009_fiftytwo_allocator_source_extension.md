# exp-20260610-009 Artifact

## Decision

`rejected_fiftytwo_week_high_allocator_source_extension` (full-stack verdict: `reject`)

## Fixed Policy Bundle

Accepted source-priority allocator with 52-week-high proximity core-flow added as rank 2 after volatility relief and before rolling peer shock. Existing top-1/day, $4,000 paper notional, 10-day hold, 12-day ticker cooldown, and default-off paper-only semantics remain fixed.

## Three-Window Before/After

| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | DD d | Trades | 52w selected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.5155 | +0.3527 | +0.4450 | $117,072.92 | $120,691.70 | $+3,618.78 | $+4,308.44 | +0.0021 | 104 | 14 |
| mid_weak | 2.1402 | 2.5950 | +0.4548 | +0.3236 | $78,110.11 | $86,503.98 | $+8,393.87 | $+5,979.77 | +0.0026 | 111 | 16 |
| old_thin | 0.5911 | 0.8029 | +0.2118 | +0.1285 | $39,667.96 | $46,414.86 | $+6,746.90 | $+4,214.31 | -0.0057 | 112 | 20 |

- Aggregate EV delta: `+1.0193`
- Aggregate PnL delta: `$+18,759.55`
- Target trades: `327`
- Binding Gate failures: `accepted_allocator_window_comparator_regression`

## Full-Stack Blocks

```json
{
  "execution_envelope": {
    "base_notional": 4000.0,
    "complete": false,
    "kill_switch_drawdown_pct": null,
    "max_capital_pct": 0.32,
    "max_concurrent": 8,
    "max_displacement": 1,
    "min_dollar_volume": 75000000.0,
    "missing": [
      "kill_switch_drawdown_pct",
      "sleeve_drawdown_stop_pct"
    ],
    "notes": "Top-1/day accepted-helper allocator, fixed $4,000 paper notional, 8 max active default-off paper positions, 10-trading-day hold, and 12-trading-day same-ticker cooldown. Source helpers keep their own liquidity guards; the 52-week source requires at least $75M 20-day average dollar volume. This experiment is not live-ready because the allocator still needs a dedicated realized-ledger kill switch before any trade_enabled=true release.",
    "order_semantics": "next_open_paper_only",
    "sleeve_drawdown_stop_pct": null,
    "slippage_bps": 5.0
  },
  "gate4_canonical": {
    "hard_failures": [],
    "status": "passed"
  },
  "gate4_strict_materiality": {
    "hard_failures": [
      "immaterial_effect"
    ],
    "status": "blocked"
  },
  "live_readiness": {
    "blockers": [
      "forward_rows_immature:0/30",
      "forward_pnl_not_positive",
      "replacement_value_not_passed",
      "execution_envelope_incomplete",
      "kill_switch_parity_not_passed"
    ],
    "closed_forward_trades": 0,
    "envelope_missing": [
      "kill_switch_drawdown_pct",
      "sleeve_drawdown_stop_pct"
    ],
    "forward_pnl": null,
    "kill_switch_parity_passed": false,
    "min_closed_forward_trades": 30,
    "ready": false,
    "replacement_value_passed": false
  },
  "verdict": "reject",
  "window_metrics": {
    "adjusted_trade_count": 327,
    "adjusted_window_count": 3,
    "aggregate_ev_delta": 1.0193,
    "aggregate_pnl_delta": 18759.55,
    "avg_pnl_per_trade_delta": 57.37,
    "avg_return_delta_pp": 1.4342,
    "baseline_hhi_concentration": 0.35,
    "baseline_single_ticker_positive_share": 0.5,
    "baseline_top_5_contribution_pct": 0.6,
    "hhi_concentration": 0.018517,
    "max_drawdown_worse_max": 0.0026,
    "single_ticker_positive_share": 0.054741,
    "top_5_contribution_pct": 0.195163,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0
  }
}
```

## Production Parity

The fixed source-extension replay failed its binding accepted-allocator comparator, so shared allocator, run.py daily snapshot wiring, and parity test changes were rolled back. No production helper, report, paper ledger, ranking, sizing, watchlist, exit, LLM, news, or order surface retains this rejected source admission.

## Reflection

The source overlapped too much with higher-priority allocator rows or displaced better rows in at least one canonical window.

No JavaScript was used.
