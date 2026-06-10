# exp-20260610-008 Artifact

## Decision

`accepted_fiftytwo_week_high_proximity_core_flow_shared_default_off_adapter` (full-stack verdict: `accepted_paper_pending_forward`)

## Fixed Policy Bundle

Liquid sector-known stock universe, close within 3% of the trailing 252-trading-day high AND a new 60-day-high breakout, 20-day SPY-relative leadership, signal-day return, close location, volume and volatility guards, same-day core A/B entry-flow confirmation, same-ticker selected-core overlap exclusion, top-1/day, fixed $4,000 paper notional, next-open entry, 10-trading-day close exit, slippage, round-trip cost, and 10-trading-day same-ticker cooldown.

## Three-Window Before/After

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2549 | +0.0921 | $117,072.92 | $118,886.44 | $+1,813.52 | +0.0027 | 289 | 14 |
| mid_weak | 2.1402 | 2.3973 | +0.2571 | $78,110.11 | $82,946.30 | $+4,836.19 | -0.0001 | 207 | 20 |
| old_thin | 0.5911 | 0.6727 | +0.0816 | $39,667.96 | $42,313.59 | $+2,645.63 | -0.0007 | 283 | 20 |

- Aggregate EV delta: `+0.4308`
- Aggregate PnL delta: `$+9,295.34`
- Target trades: `54`
- Gate failures: `none`

## Full-Stack Contract Blocks

```json
{
  "execution_envelope": {
    "base_notional": 4000.0,
    "complete": true,
    "kill_switch_drawdown_pct": 0.08,
    "max_capital_pct": 0.4,
    "max_concurrent": 10,
    "max_displacement": 1,
    "min_dollar_volume": 75000000.0,
    "missing": [],
    "notes": "Top-1/day with a 10-trading-day hold bounds concurrency at 10 paper positions x $4,000 = $40,000 committed paper capital (40% of the $100,000 backtest equity base). Kill switch (8% of committed capital realized peak-to-trough drawdown, hard) and sleeve drawdown stop (5%, soft) plus a positive-PnL concentration kill are implemented in quant/fiftytwo_week_high_proximity_paper_sleeve.py and parity-tested; when triggered the sleeve stops creating new pending paper entries. All values declared up front so live promotion is a checklist item, not a new alpha search.",
    "order_semantics": "next_open",
    "sleeve_drawdown_stop_pct": 0.05,
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
      "replacement_value_not_passed"
    ],
    "closed_forward_trades": 0,
    "envelope_missing": [],
    "forward_pnl": null,
    "kill_switch_parity_passed": true,
    "min_closed_forward_trades": 30,
    "ready": false,
    "replacement_value_passed": false
  },
  "materiality_note": "Per docs/agent_experiment_protocol.md, the scout materiality floor ($500/trade or 5pp) is calibrated for support-field/notional-scalar scouts; at the fixed $4,000 candidate-pool paper notional it would reject every accepted comparator. The binding materiality standard for candidate-pool sources is beating the closest accepted comparator after costs, which this run enforces in the canonical framework Gate 4. Both evaluate_gate4 blocks are recorded.",
  "next_step": "Accept as a default-off paper sleeve now. No new experiment is needed to reach live -- only resolve the remaining Gate-5 items as forward evidence matures: forward_rows_immature:0/30, forward_pnl_not_positive, replacement_value_not_passed.",
  "verdict": "accepted_paper_pending_forward",
  "window_metrics": {
    "adjusted_trade_count": 54,
    "adjusted_window_count": 3,
    "aggregate_ev_delta": 0.4308,
    "aggregate_pnl_delta": 9295.34,
    "avg_pnl_per_trade_delta": 172.14,
    "avg_return_delta_pp": 4.3034,
    "baseline_hhi_concentration": 0.35,
    "baseline_single_ticker_positive_share": 0.5,
    "baseline_top_5_contribution_pct": 0.6,
    "hhi_concentration": 0.075653,
    "max_drawdown_worse_max": 0.0027,
    "single_ticker_positive_share": 0.18657,
    "top_5_contribution_pct": 0.497929,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0
  }
}
```

## Production Parity

Historical replay and daily observation share quant/fiftytwo_week_high_proximity_paper_sleeve.py. The helper is default-off and cannot alter orders, core ranking, sizing, exits, watchlists, LLM, or news behavior. The sleeve kill switch only stops new paper entries; it never touches orders.

The candidate rule needs >= 252 prior trading days of OHLCV. With less history the rule fails closed in both historical replay and daily snapshots: the ticker simply cannot qualify. Historical replay loads a deep snapshot (470 calendar days of lookback) of past bars only; no future data is read.

## Reflection

The shared helper reproduced the private replay lead because it kept the exact 252-day-high proximity, 60-day breakout, leadership and quality gates, core-flow admission, same-ticker overlap exclusion, next-open entry, 10-day exit, cost, top-1, and cooldown semantics while adding daily pending/open/closed state handling, a fail-closed >=252-day history requirement, and a realized-drawdown kill switch that only blocks new paper entries.

No JavaScript was used.
