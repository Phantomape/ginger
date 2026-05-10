# exp-20260510-018 Effective Slot Accounting Scout

## Decision

- decision: rejected
- all slot-missed count: 25
- all slot-missed PnL: 8330.63
- all slot-missed win rate: 0.4
- positive windows: 1
- single ticker positive share: 0.4652
- gate failures: all_slot_missed_win_rate_lt_50pct, positive_windows_lt_2

## Deterministic Slices

- all_slot_missed_upper_bound: count=25, pnl=8330.63, win_rate=0.4, tickers={'AMD': -1948.94, 'APP': 8242.48, 'AVGO': -178.38, 'CVX': 530.73, 'DDOG': -3681.13, 'DE': -362.18, 'GLD': 45.57, 'GOOG': -289.57, 'GS': 92.23, 'IAU': 763.74, 'IWM': -274.69, 'JPM': -29.94, 'LLY': -126.09, 'MA': 143.42, 'META': -1477.08, 'PLTR': 3970.56, 'SLV': -228.28, 'SPOT': 1267.24, 'TRIP': -791.11, 'TSLA': 2662.05}
- first_slot_missed_per_day: count=16, pnl=6934.96, win_rate=0.5, tickers={'APP': 8242.48, 'AVGO': -178.38, 'CVX': 530.73, 'DDOG': -2374.44, 'DE': -362.18, 'GLD': 45.57, 'GOOG': -289.57, 'GS': 92.23, 'IAU': 763.74, 'IWM': -255.16, 'MA': 143.42, 'META': -1092.82, 'PLTR': 1193.21, 'SPOT': 1267.24, 'TRIP': -791.11}
- one_extra_slot_slice_slot_sliced_only: count=6, pnl=2568.43, win_rate=0.6667, tickers={'GLD': 45.57, 'GS': 92.23, 'IWM': -255.16, 'MA': 143.42, 'META': -1092.82, 'PLTR': 3635.19}
- breakout_release_slice_requires_slots_gt_1: count=10, pnl=4366.53, win_rate=0.4, tickers={'APP': 8242.48, 'AVGO': -178.38, 'CVX': 530.73, 'DDOG': -2374.44, 'DE': -362.18, 'GOOG': -289.57, 'IAU': 763.74, 'PLTR': -2441.98, 'SPOT': 1267.24, 'TRIP': -791.11}

## By Window

- late_strong: count=3, pnl=-3296.92, win_rate=0.0, reasons={'adverse_gap_down_cancel': 5, 'entered': 19, 'gap_cancel': 4, 'no_future_fill': 1, 'no_shares': 9, 'slot_sliced': 3}
- mid_weak: count=5, pnl=-1466.87, win_rate=0.4, reasons={'adverse_gap_down_cancel': 1, 'entered': 21, 'gap_cancel': 4, 'no_shares': 11, 'scarce_slot_breakout_deferred': 4, 'slot_sliced': 1}
- old_thin: count=17, pnl=13094.42, win_rate=0.4706, reasons={'adverse_gap_down_cancel': 1, 'entered': 22, 'gap_cancel': 5, 'no_shares': 10, 'scarce_slot_breakout_deferred': 8, 'slot_sliced': 9}

## Live 2026-05-08 Context

- active_positions=10, max_positions=5, available_slots=0, heat=0.0179, can_add_new_positions=True
- deferred_breakouts=[{'ticker': 'MU', 'strategy': 'breakout_long', 'sector': 'Technology', 'available_slots': 0, 'trade_quality_score': 0.906, 'confidence_score': 1.0, 'pct_from_52w_high': None, 'entry_price': 746.81, 'stop_price': 687.87, 'target_price': 923.64, 'min_index_pct_from_ma': None}]

## Notes

- Observed-only fixed-notional replacement-value scout.
- Does not change production signals, sizing, orders, ranking, exits, prompts, or core slots.
- `scarce_slot_breakout_deferred` rows require slots greater than the current breakout defer threshold, not just one extra nominal slot.
