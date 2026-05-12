# exp-20260512-012 SEC financial-report entry-gap notional

Decision: `rejected_entry_gap_nonnegative_notional_scalar`

## Hypothesis

Inside the accepted SEC financial-report T+1 paper sleeve, a nonnegative T+2 opening gap versus prior close is an execution-time confirmation that the positive filing reaction has not faded; those paper entries may deserve a modest higher notional without changing queue eligibility, ranking, capacity, hold days, or live orders.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Sleeve trades | Gap bucket trades | Max DD d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.565792 | 4.737248 | +0.171456 | $100,825.38 | $104,489.84 | $+3,664.46 | 14 | 7 | -0.1161% |
| mid_weak | 2.744065 | 3.251316 | +0.507251 | $80,159.13 | $88,481.14 | $+8,322.01 | 16 | 13 | -0.2447% |
| old_thin | 0.795586 | 0.783807 | -0.011779 | $44,550.91 | $44,637.80 | $+86.89 | 22 | 6 | +0.9226% |

## Aggregate

- Best scalar: `1.50`
- EV delta: `+0.666928`
- Total PnL delta: `$+12,073.36`
- Sleeve PnL delta: `$+11,723.96`
- Gate passed: `False`

## Protocol Answers

{
  "1_alpha_hypothesis": "risk allocation: scale paper notional only for accepted SEC financial-report T+1 sleeve entries whose T+2 open is nonnegative versus prior close.",
  "2_history_check": "exp-20260512-001 accepted the T+1 excess floor; exp-20260512-006 accepted global $15k notional; exp-20260512-007 accepted periodic-report family notional; exp-20260512-009 rejected queue-rank notional; exp-20260512-011 rejected clean earnings 8-K notional. No logged SEC financial-report run isolated T+2 fill-gap confirmation.",
  "3_single_causal_variable": "nonnegative T+2 entry-gap paper-notional scalar only",
  "4_acceptance_standard": "Three fixed windows, aggregate EV and sleeve PnL improve, EV/PnL improve in all three windows, max drawdown drift <=0.5pp, at least 40 closed sleeve trades, and at least 20 closed nonnegative-gap trades.",
  "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260512_012_sec_financial_report_entry_gap_notional.py"
}

## Production Impact

{
  "alters_candidate_ranking": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": true,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "parity_test_added": false,
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
