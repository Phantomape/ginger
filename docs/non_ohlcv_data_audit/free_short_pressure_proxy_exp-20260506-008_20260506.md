# Free Regulatory Short Pressure Proxy Shadow Experiment

- Experiment: `exp-20260506-008`
- Status: `observed_only`
- Decision: `shadow_only`
- Production impact: `{'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'production_signal_path_changed': False}`

## Sources

- FINRA short interest: https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files
- SEC fails-to-deliver: https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data
- Nasdaq Reg SHO threshold: https://nasdaqtrader.com/trader.aspx?id=RegSHOThreshold

## Coverage

- Candidates tagged: `66` / `66`
- SEC FTD files OK: `25` / `26`
- SEC FTD candidates with recent positive FTD: `56`
- Nasdaq threshold files OK: `53` / `53`
- Nasdaq threshold candidate matches: `0`

## Shadow Result

- High free proxy: `{'count': 17, 'forward_5d_count': 17, 'forward_5d_mean': 0.004765, 'forward_5d_median': -0.008582, 'forward_10d_count': 17, 'forward_10d_mean': 0.009763, 'forward_10d_median': -0.002575, 'forward_20d_count': 17, 'forward_20d_mean': 0.016335, 'forward_20d_median': 0.009709, 'forward_60d_count': 15, 'forward_60d_mean': 0.111681, 'forward_60d_median': 0.093793, 'realized_trade_count': 8, 'realized_pnl_pct_mean': 0.014819, 'realized_win_rate': 0.375}`
- Non-high free proxy: `{'count': 49, 'forward_5d_count': 49, 'forward_5d_mean': 0.0281, 'forward_5d_median': 0.026472, 'forward_10d_count': 49, 'forward_10d_mean': 0.03476, 'forward_10d_median': 0.026909, 'forward_20d_count': 45, 'forward_20d_mean': 0.042323, 'forward_20d_median': 0.031561, 'forward_60d_count': 44, 'forward_60d_mean': 0.090071, 'forward_60d_median': 0.105466, 'realized_trade_count': 25, 'realized_pnl_pct_mean': 0.064086, 'realized_win_rate': 0.68}`
- High free proxy + breakout_long: `{'count': 7, 'forward_5d_count': 7, 'forward_5d_mean': 0.006901, 'forward_5d_median': -0.016767, 'forward_10d_count': 7, 'forward_10d_mean': 0.004093, 'forward_10d_median': -0.002575, 'forward_20d_count': 7, 'forward_20d_mean': 0.003127, 'forward_20d_median': 0.001687, 'forward_60d_count': 7, 'forward_60d_mean': -0.009127, 'forward_60d_median': -0.050082, 'realized_trade_count': 4, 'realized_pnl_pct_mean': 0.009335, 'realized_win_rate': 0.25}`
- Other breakout_long: `{'count': 20, 'forward_5d_count': 20, 'forward_5d_mean': 0.038814, 'forward_5d_median': 0.031181, 'forward_10d_count': 20, 'forward_10d_mean': 0.056676, 'forward_10d_median': 0.029596, 'forward_20d_count': 18, 'forward_20d_mean': 0.060124, 'forward_20d_median': 0.067061, 'forward_60d_count': 18, 'forward_60d_mean': 0.094236, 'forward_60d_median': 0.11489, 'realized_trade_count': 10, 'realized_pnl_pct_mean': 0.075378, 'realized_win_rate': 0.9}`
- Slot conflict audit: `{'slot_conflict_count': 5, 'high_free_proxy_slot_conflict_count': 1, 'high_free_proxy_slot_conflict_forward_20d_mean': -0.011912, 'entered_non_high_forward_20d_mean': 0.059584, 'scarce_slot_opportunity_cost_20d': -0.071496}`
- Delta observations: `{'high_minus_non_high_forward_20d': -0.025988, 'expected_value_score_delta': None, 'reason_ev_delta_null': 'No production replay or portfolio ordering change was made.'}`

## Decision

Shadow-only: the free regulatory proxy bundle adds SEC FTD and Nasdaq threshold flags to FINRA short interest, but these are indirect stress proxies rather than true borrow fee / availability data. No production rule is justified without multi-window replay and a stronger slot-value edge.

## Next Minimal Action

If the shadow bucket improves versus FINRA-only, run the same proxy over the fixed three-window snapshot set; otherwise stop at audit/shadow.
