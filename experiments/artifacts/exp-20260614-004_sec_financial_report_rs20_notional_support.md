# exp-20260614-004 SEC financial-report RS20 notional support

Decision: `accepted_default_off_sec_financial_report_rs20_leader_notional_1.15x`

## Hypothesis

SEC financial-report T+1 drift candidates that are already 20-day SPY-relative leaders may deserve bounded default-off paper notional support because price confirmation before entry may distinguish durable institutional absorption from one-day filing drift noise.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Sleeve trades | RS20 bucket trades | Max DD d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.513117 | 5.575273 | +0.062156 | $124,033.00 | $125,149.12 | $+1,116.12 | 14 | 5 | -0.0421% |
| mid_weak | 3.020826 | 3.103958 | +0.083132 | $93,321.34 | $94,774.48 | $+1,453.14 | 16 | 8 | -0.0657% |
| old_thin | 0.948373 | 0.961269 | +0.012896 | $53,342.93 | $54,009.05 | $+666.12 | 22 | 11 | +0.2758% |

## Aggregate

- Best scalar: `1.15`
- EV delta: `+0.158184`
- Total PnL delta: `$+3,235.38`
- Sleeve PnL delta: `$+3,222.91`
- Gate passed: `True`

## Protocol Answers

{
  "1_alpha_hypothesis": "capital allocation: scale paper notional only for fixed accepted SEC financial-report T+1 sleeve entries whose pre-entry 20-session ticker-vs-SPY excess return is >= 5pp.",
  "2_history_check": "exp-20260512-001 accepted the T+1 excess floor; exp-20260512-006 accepted global $15k notional; exp-20260512-007 accepted periodic-report family notional; exp-20260512-009 rejected queue-rank notional; exp-20260512-011 rejected clean earnings 8-K notional; exp-20260512-012 rejected entry-gap notional. exp-20260510-029 left RS20 filing drift only as an observed-only lead, not a current paper-sleeve Gate 1-4 allocation result.",
  "3_single_causal_variable": "RS20 >= 5pp paper-notional scalar only on the fixed SEC financial-report queue",
  "4_acceptance_standard": "Three fixed windows, aggregate EV and sleeve PnL improve, EV/PnL improve in all three windows, max drawdown drift <=0.5pp, at least 40 closed sleeve trades, and at least 20 closed RS20-leader trades.",
  "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260614_004_sec_financial_report_rs20_notional_support.py"
}

## Production Impact

{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": true,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "parity_test_added": true,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": true,
  "shared_policy_modules": [
    "quant/sec_event_queue.py",
    "quant/sec_financial_report_event_sleeve.py"
  ]
}

## Post-Run Reflection

{
  "forbidden_near_neighbor_retry": "Do not retune this same SEC financial-report RS lookback, 5pp threshold, or 1.15x scalar without forward replacement-value evidence or a materially new free-data discriminator.",
  "new_evidence_required": "Closed forward daily paper outcomes, concentration/capacity checks, and a live-realistic execution envelope are required before any live-ready promotion.",
  "why_result_happened": "The RS20 leader bucket appears to capture durable pre-entry institutional absorption inside the already accepted SEC financial-report T+1 drift queue. The support bucket had 24 closed trades across the three fixed windows, improved EV/PnL in every window, and left survival and trade count unchanged."
}

## Live-Realistic Envelope

{
  "capacity_cap": "DEFAULT_MAX_POSITIONS remains 3; core slots unchanged",
  "kill_switch": "Keep config default-off/trade_enabled false; disable rs20_leader_notional_enabled if forward paper drift degrades.",
  "live_ready": false,
  "order_semantics": "no live orders emitted; paper ledger only",
  "paper_notional_rule": "Existing SEC financial-report paper notional multiplied by 1.15 only when pre-entry ticker_minus_spy_ret20 >= 0.05.",
  "scope": "accepted default-off paper helper only",
  "slippage_liquidity": "Not evaluated for live execution; current result is paper-only and uses existing round_trip_cost_pct.",
  "trade_enabled": false
}
