# exp-20260620-008 Artifact

## Decision

`rejected_supplier_financing_debt_relief_shared_risk_scaled_default_off_adapter` (full-stack verdict: `reject`)

## Fixed Policy Bundle

Raw SEC Companyfacts quarterly accounts-payable DPO extension AND annual principal debt/revenue burden relief, filed-date PIT, signal-date OHLCV leadership/quality confirmation, top-1/day, 10-trading-day same-ticker cooldown, next-open paper entry, 10-trading-day close exit, costs, and one-way PIT 20d volatility/ADV20 paper-notional scaling.

## Three-Window Before/After

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4404 | +0.2776 | $117,072.92 | $120,627.75 | $+3,554.83 | -0.0007 | 145 | 32 |
| mid_weak | 2.1402 | 2.4969 | +0.3567 | $78,110.11 | $85,219.11 | $+7,109.00 | -0.0026 | 198 | 36 |
| old_thin | 0.5911 | 0.6369 | +0.0458 | $39,667.96 | $41,359.61 | $+1,691.65 | +0.0016 | 89 | 20 |

- Aggregate EV delta: `+0.6801`
- Aggregate PnL delta: `$+12,355.48`
- Target trades: `88`
- Gate failures: `positive_lead_not_reproduced_by_shared_adapter`

## Full-Stack Blocks

```json
{
  "execution_envelope": {
    "base_notional": 4000.0,
    "complete": true,
    "kill_switch_drawdown_pct": 0.08,
    "max_capital_pct": 0.4,
    "max_concurrent": 10,
    "max_displacement": 1,
    "min_dollar_volume": 50000000.0,
    "missing": [],
    "notes": "Top-1/day with a 10-trading-day hold bounds default-off paper concurrency at roughly 10 positions. Base $4,000 paper notional is scaled one-way to 0.35x-1.00x using PIT 20d realized volatility and ADV20; the envelope never upsizes. Live activation remains blocked until forward replacement-value rows and kill-switch parity mature.",
    "order_semantics": "next_open",
    "sleeve_drawdown_stop_pct": 0.05,
    "slippage_bps": 5.0
  },
  "lead_reproduction": {
    "aggregate_expected_value_score_delta_drift": -1.0718,
    "aggregate_total_pnl_delta_drift": -18533.21,
    "by_window": {
      "late_strong": {
        "expected_value_score_drift": -0.4167,
        "source_target_trade_count": 32,
        "target_trade_count": 32,
        "total_pnl_drift": -5332.29
      },
      "mid_weak": {
        "expected_value_score_drift": -0.5808,
        "source_target_trade_count": 36,
        "target_trade_count": 36,
        "total_pnl_drift": -10663.46
      },
      "old_thin": {
        "expected_value_score_drift": -0.0743,
        "source_target_trade_count": 20,
        "target_trade_count": 20,
        "total_pnl_drift": -2537.46
      }
    },
    "max_ev_drift": 0.0002,
    "max_pnl_drift": 1.0,
    "passed": false,
    "source_lead_artifact": "data/experiments/exp-20260620-007/exp_20260620_007_supplier_financing_debt_relief_risk_scaled_notional.json",
    "source_lead_experiment_id": "exp-20260620-007",
    "trade_count_drift": 0
  },
  "live_readiness": {
    "blockers": [
      "forward_rows_immature:0/30",
      "forward_pnl_not_positive",
      "replacement_value_not_passed",
      "kill_switch_parity_not_passed"
    ],
    "closed_forward_trades": 0,
    "envelope_missing": [],
    "forward_pnl": null,
    "kill_switch_parity_passed": false,
    "min_closed_forward_trades": 30,
    "ready": false,
    "replacement_value_passed": false
  },
  "next_step": "Roll back the sleeve change and log the failure. The shared helper did not reproduce the positive lead or pass Gate 4.",
  "verdict": "reject",
  "window_metrics": {
    "adjusted_trade_count": 88,
    "adjusted_window_count": 3,
    "aggregate_ev_delta": 0.6801,
    "aggregate_pnl_delta": 12355.48,
    "avg_pnl_per_trade_delta": 140.40318181818182,
    "hhi_concentration": 0.233723,
    "max_drawdown_worse_max": 0.0016,
    "single_ticker_positive_share": 0.294408,
    "top_5_contribution_pct": 0.986391498354153,
    "windows_ev_improved": 3,
    "windows_ev_regressed": 0,
    "windows_pnl_improved": 3,
    "windows_pnl_regressed": 0
  }
}
```

## Production Parity

Historical replay and daily observation share quant/supplier_financing_debt_relief_paper_sleeve.py. The helper is default-off and cannot alter orders, core ranking, sizing, exits, watchlists, LLM, or news behavior.

## Reflection

The shared helper did not reproduce the private replay lead or failed the canonical windows, implying the lead depended on runner-local details or remained too fragile after shared daily semantics.

No JavaScript was used.
