# Short Interest / Borrow Pressure PIT Coverage + Shadow Experiment

- Experiment: `exp-20260505-024`
- Run timestamp: `2026-05-06T01:25:22+00:00`
- Source: FINRA official biweekly equity short-interest CSV files
- Source URLs: `https://www.finra.org/finra-data/browse-catalog/equity-short-interest/files`, `https://www.finra.org/filing-reporting/regulatory-filing-systems/short-interest`
- Production impact: `{'shared_policy_changed': False, 'backtester_adapter_changed': False, 'run_adapter_changed': False, 'replay_only': True, 'parity_test_added': False, 'production_signal_path_changed': False}`
- Decision: `shadow_only`

## Hypothesis

High short-interest crowding is not a standalone long signal; it may add value only as an overlay on existing breakout/event-confirmed candidates. Without borrow-fee or float-short data, confidence must be downgraded.

## Data Availability / PIT Status

- Candidate rows: `66`
- Tagged candidate rows: `66`
- PIT-safe tagged rows: `66`
- Coverage: `100.00%`
- FINRA files fetched: `23` ok / `23` attempted
- Tickers covered: `31` / `31`
- `short_interest_float`: unavailable from FINRA CSV
- `borrow_fee`, `shares_available`, `hard_to_borrow`: unavailable
- `daily_short_volume_ratio`: intentionally not used; daily short volume is activity, not short-interest positioning

## Shadow Results

- High short alone: `{'count': 17, 'forward_5d_count': 17, 'forward_5d_mean': 0.012058, 'forward_5d_median': 0.001099, 'forward_10d_count': 17, 'forward_10d_mean': 0.027138, 'forward_10d_median': 0.027042, 'forward_20d_count': 17, 'forward_20d_mean': 0.021649, 'forward_20d_median': 0.001687, 'forward_60d_count': 15, 'forward_60d_mean': 0.067508, 'forward_60d_median': 0.031669, 'realized_trade_count': 9, 'realized_pnl_pct_mean': 0.012689, 'realized_win_rate': 0.333333}`
- Non-high short: `{'count': 49, 'forward_5d_count': 49, 'forward_5d_mean': 0.02557, 'forward_5d_median': 0.026472, 'forward_10d_count': 49, 'forward_10d_mean': 0.028731, 'forward_10d_median': 0.013376, 'forward_20d_count': 45, 'forward_20d_mean': 0.040315, 'forward_20d_median': 0.031561, 'forward_60d_count': 44, 'forward_60d_mean': 0.10513, 'forward_60d_median': 0.105466, 'realized_trade_count': 24, 'realized_pnl_pct_mean': 0.066938, 'realized_win_rate': 0.708333}`
- High short + breakout_long: `{'count': 9, 'forward_5d_count': 9, 'forward_5d_mean': 0.01615, 'forward_5d_median': 0.001099, 'forward_10d_count': 9, 'forward_10d_mean': 0.0332, 'forward_10d_median': 0.02711, 'forward_20d_count': 9, 'forward_20d_mean': 0.032034, 'forward_20d_median': 0.001687, 'forward_60d_count': 9, 'forward_60d_mean': 0.02222, 'forward_60d_median': -0.050082, 'realized_trade_count': 5, 'realized_pnl_pct_mean': 0.030751, 'realized_win_rate': 0.4}`
- Other breakout_long: `{'count': 18, 'forward_5d_count': 18, 'forward_5d_mean': 0.037736, 'forward_5d_median': 0.031181, 'forward_10d_count': 18, 'forward_10d_mean': 0.047965, 'forward_10d_median': 0.027844, 'forward_20d_count': 16, 'forward_20d_mean': 0.050988, 'forward_20d_median': 0.054578, 'forward_60d_count': 16, 'forward_60d_mean': 0.089524, 'forward_60d_median': 0.113726, 'realized_trade_count': 9, 'realized_pnl_pct_mean': 0.070819, 'realized_win_rate': 0.888889}`
- Slot conflict audit: `{'slot_conflict_count': 5, 'high_short_slot_conflict_count': 1, 'high_short_slot_conflict_forward_20d_mean': -0.011912, 'entered_non_high_forward_20d_mean': 0.053282, 'scarce_slot_opportunity_cost_20d': -0.065194}`
- False-positive examples: `[{'window': 'primary', 'date': '2026-01-06', 'ticker': 'ISRG', 'strategy': 'breakout_long', 'decision': 'no_shares', 'days_to_cover': 4.57, 'short_interest_change_pct': -2.69, 'pnl_pct_net': None, 'forward_20d': -0.192899}, {'window': 'primary', 'date': '2026-02-19', 'ticker': 'DE', 'strategy': 'trend_long', 'decision': 'no_shares', 'days_to_cover': 4.77, 'short_interest_change_pct': 9.06, 'pnl_pct_net': None, 'forward_20d': -0.142628}, {'window': 'primary', 'date': '2026-01-16', 'ticker': 'TSM', 'strategy': 'trend_long', 'decision': 'entered', 'days_to_cover': 2.81, 'short_interest_change_pct': -5.43, 'pnl_pct_net': -0.060734, 'forward_20d': 0.063668}, {'window': 'primary', 'date': '2026-01-06', 'ticker': 'GS', 'strategy': 'breakout_long', 'decision': 'entered', 'days_to_cover': 3.13, 'short_interest_change_pct': 5.38, 'pnl_pct_net': -0.039653, 'forward_20d': -0.044135}, {'window': 'secondary', 'date': '2025-07-18', 'ticker': 'TSM', 'strategy': 'trend_long', 'decision': 'entered', 'days_to_cover': 2.6, 'short_interest_change_pct': 4.43, 'pnl_pct_net': -0.038208, 'forward_20d': -0.006323}, {'window': 'primary', 'date': '2026-01-06', 'ticker': 'XOM', 'strategy': 'breakout_long', 'decision': 'entered', 'days_to_cover': 2.95, 'short_interest_change_pct': 5.14, 'pnl_pct_net': -0.030081, 'forward_20d': 0.219248}, {'window': 'secondary', 'date': '2025-08-01', 'ticker': 'META', 'strategy': 'trend_long', 'decision': 'entered', 'days_to_cover': 2.55, 'short_interest_change_pct': -18.94, 'pnl_pct_net': -0.027155, 'forward_20d': -0.01508}, {'window': 'secondary', 'date': '2025-10-23', 'ticker': 'ISRG', 'strategy': 'breakout_long', 'decision': 'entered', 'days_to_cover': 3.27, 'short_interest_change_pct': 43.9, 'pnl_pct_net': -0.001338, 'forward_20d': 0.001687}]`

## Decision

Shadow-only: official FINRA short-interest positioning is PIT-safe when joined by publication date, but this run found no borrow pressure fields, no float-short field, and only observational candidate stratification. No production rule or default-off replay is justified yet.

## Next Minimal Action

Add a read-only FINRA adapter/cache that persists settlement_date, publication_date, usable_trade_date, short_interest, days_to_cover, and change_percent; then rerun this shadow study on three non-overlapping windows.
