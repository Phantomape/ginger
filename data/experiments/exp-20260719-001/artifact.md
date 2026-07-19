# exp-20260719-001: deps.dev Maven release acceleration

- Status: `rejected`
- Decision: `rejected_deps_dev_maven_release_acceleration`
- Policy: completed Monday-Sunday count >=2 and strictly above the prior-eight-week median; weekly top 3; next open; tenth-session close.
- Capital: 24% funded sleeve + 76% accepted core; default-off; no orders.
- Source event SHA-256: `8a3e33dd703f7d3633ae5bd4843b38d26b68c32ee4639f68854ac761cd25d570`

## Outcome-blind source density

| Window | Eligible issuer-weeks | Tickers | Top-1 share | Pass |
|---|---:|---:|---:|:---:|
| old_thin | 59 | 12 | 23.73% | yes |
| mid_weak | 50 | 12 | 24.00% | yes |
| late_strong | 51 | 12 | 19.61% | yes |

## Gate 1-4 replay

| Window | Settled | Tickers | EV delta | PnL delta | Cash/SPY/QQQ |
|---|---:|---:|---:|---:|:---:|
| old_thin | 36 | 12 | -0.0165 | -1297.93 | pass |
| mid_weak | 33 | 10 | -0.4532 | -12343.51 | pass |
| late_strong | 36 | 11 | -2.2157 | -29149.25 | fail |

Aggregate EV delta: `-2.6854`.
Aggregate PnL delta: `-42790.69`.
Gate 2: `pass`; Gate 3: `pass`; Gate 4: `fail`.

## Binding failures

- `non_positive_aggregate_ev`
- `non_positive_aggregate_pnl`
- `insufficient_ev_improved_windows`
- `ev_regressed_windows`
- `drawdown_worse_guardrail`
- `window_pnl_not_improved:old_thin`
- `window_pnl_not_improved:mid_weak`
- `window_pnl_not_improved:late_strong`
- `cash_spy_qqq_replacement_failed:late_strong`
- `accepted_candidate_pool_ev_comparator_not_beaten`
- `accepted_candidate_pool_pnl_comparator_not_beaten`
- `top5_positive_pnl_concentration`

The source bundle and all result JSON files are hash-bound/reproducible. This paper sleeve remains live-ineligible until forward replacement-value and kill-switch parity requirements pass.
