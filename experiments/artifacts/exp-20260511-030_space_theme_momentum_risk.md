# exp-20260511-030 Space theme momentum risk

- decision: rejected_theme_weak_space_risk_scalar
- hypothesis: risk allocation: official Space-catalyst entries should keep full accepted-stack risk only when same-theme ETF momentum confirms; when max(UFO, ARKX) 20-day momentum is negative, de-risk Space signals instead of adding noisy ticker breadth or using underpowered LLM soft-ranking.
- changed_variable: space_theme_weak_risk_scalar
- before_state: exp-20260511-021 accepted Space stack
- best_theme_weak_risk_scalar: 0.0
- expected_value_score_delta_vs_before: 0.0
- rejection_reason: No tested UFO/ARKX negative 20-day momentum risk scalar cleared the three-window gate versus the accepted exp-20260511-021 Space stack.

## Sweep

| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows | Weak signals |
|---:|---|---:|---:|---:|---:|---:|
| 0.0 | fail | +0.0000 | +0.00 | +0.0197 | 0/3 | 0 |
| 0.25 | fail | +0.0000 | +0.00 | +0.0197 | 0/3 | 0 |
| 0.5 | fail | +0.0000 | +0.00 | +0.0197 | 0/3 | 0 |
| 0.75 | fail | +0.0000 | +0.00 | +0.0197 | 0/3 | 0 |

## Best Three-Window Comparison

| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Weak signals | Theme states |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| late_strong | 4.7471 | 4.7471 | +0.0000 | +0.5131 | 102533.13 | 102533.13 | +0.00 | 0 | {"confirmed": 7} |
| mid_weak | 3.0517 | 3.0517 | +0.0000 | +1.3828 | 79675.53 | 79675.53 | +0.00 | 0 | {"confirmed": 18} |
| old_thin | 0.6919 | 0.6919 | +0.0000 | +0.3066 | 44928.42 | 44928.42 | +0.00 | 0 | {"confirmed": 12} |

## Aggregate

- core: {'expected_value_score_sum': 6.2882, 'total_pnl_sum': 184444.42, 'trade_count_sum': 62, 'min_survival_rate': 0.7925, 'max_drawdown_pct_max': 0.0941}
- before_exp021_stack: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- after_best: {'expected_value_score_sum': 8.4907, 'total_pnl_sum': 227137.08, 'trade_count_sum': 71, 'min_survival_rate': 0.807, 'max_drawdown_pct_max': 0.1012}
- gate: {'passed': False, 'aggregate_delta_vs_before': {'expected_value_score_sum': 0.0, 'total_pnl_sum': 0.0, 'trade_count_sum': 0, 'min_survival_rate': 0.0, 'max_drawdown_pct_max': 0.0}, 'aggregate_delta_vs_core': {'expected_value_score_sum': 2.2025, 'total_pnl_sum': 42692.66, 'trade_count_sum': 9, 'min_survival_rate': 0.0145, 'max_drawdown_pct_max': 0.0071}, 'windows_ev_improved_vs_before': 0, 'windows_ev_regressed_vs_before': 0, 'windows_ev_improved_vs_core': 3, 'max_drawdown_worsening_vs_core': 0.0197, 'max_drawdown_change_vs_before': 0.0, 'theme_adjusted_signal_count': 0}
- theme_weak_trade_attribution: {'trade_count': 0, 'total_pnl': 0.0, 'wins': 0, 'losses': 0, 'win_rate': None, 'single_ticker_positive_share': None, 'by_ticker': {}}

## Production Impact

{"backtester_adapter_changed": false, "live_slots": 0, "live_slots_changed": false, "parity_test_added": false, "replay_only": true, "run_adapter_changed": false, "shared_policy_changed": false}

## Interpretation

Do not add a theme ETF momentum risk gate to the Space sleeve. The accepted Space stack should stay focused on catalyst bucket and ticker/strategy lifecycle scalars, not theme ETF timing.
