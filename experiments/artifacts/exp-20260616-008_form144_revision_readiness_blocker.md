# exp-20260616-008: Form 144 / Revision Readiness Blocker

## Decision

`blocked_no_trustworthy_nonrepeat_form144_or_revision_alpha_surface`. No strategy code or production path changed.

## Alpha Hypothesis

Form 144 planned-sale absorption and analyst-revision breadth remain the strongest free-data candidate-pool directions, but they are executable only if independent PIT sale-size/role/float or historical breadth/dispersion fields exist.

## History Check

- `exp-20260612-023`: `rejected_form144_sale_notice_absorption_candidate_pool`; EV delta `1.7976`; PnL delta `35180.13`.
- `exp-20260613-013`: `rejected_form144_isolated_sale_notice_absorption_candidate_pool`; EV delta `1.4394`; PnL delta `22080.96`.
- `exp-20260616-002`: `blocked_no_gate4_ready_nonrepeat_alpha_candidate`; EV delta `None`; PnL delta `None`.
- `exp-20260616-006`: `blocked_seasoned_new_listing_independent_data_absent`; EV delta `None`; PnL delta `None`.
- `exp-20260615-029`: `rejected_sec_named_counterparty_contract_economics_candidate_pool`; EV delta `-0.1094`; PnL delta `-906.58`.
- `exp-20260615-024`: `rejected_no_alpha`; EV delta `None`; PnL delta `None`.

## Gate 1-4

- Gate 1: baseline `data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: failed intentionally; no executable rows because required independent fields are missing. Future rows still require `entry_date` and `target_price`.
- Gate 3: no filter added; baseline survival `0.8232`, minimum window survival `0.7925`.
- Gate 4: no strategy launched; before/after are unchanged in all canonical windows.

| window | EV before | EV after | EV delta | PnL before | PnL after | PnL delta | trades before | trades after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 5.1628 | 5.1628 | 0.0000 | 117072.92 | 117072.92 | 0.00 | 18 | 18 |
| mid_weak | 2.1402 | 2.1402 | 0.0000 | 78110.11 | 78110.11 | 0.00 | 21 | 21 |
| old_thin | 0.5911 | 0.5911 | 0.0000 | 39667.96 | 39667.96 | 0.00 | 22 | 22 |

## Blocker Proof

- Form 144 missing fields: `planned_sale_value, planned_sale_shares, securities_to_be_sold, seller_name, holder_role, relationship_to_issuer, sale_pct_float, public_float`.
- Revision historical missing fields: `analyst_count_current_qtr, analyst_count_next_qtr, estimate_dispersion, fiscal_period, revenue_estimate_current_qtr, revenue_estimate_next_qtr, vendor_asof`.
- Latest revision matched candidate rows: `0`.

## Production / Backtest Parity

No production/backtest behavior changed. A future positive must use a shared default-off helper in both historical replay and daily snapshots.

## Reflection

The alpha idea is directionally attractive, but the repository only has Form 144 index/event rows and EPS-centric revision snapshots. Those surfaces cannot isolate the promised causal edge, so launching a strategy would measure a frozen near-neighbor rather than a new candidate-pool alpha.

## Forbidden Near-Neighbor Retry

Do not retry Form 144 top-N, OHLCV gates, hold days, notional, cooldown, liquidity, or price-confirmation variants. Do not retry EPS-only revision thresholds, DTE windows, or revision-direction rankers. Do not relaunch SEC text counterparty variants without a new structured economics field.

## New Evidence Required

Required new evidence is PIT parsed Form 144 planned-sale shares or value, holder role, relationship-to-issuer, public float and sale_pct_float, or historical/forward analyst-count, revenue-estimate, dispersion, vendor_asof, and fiscal-period coverage with closed candidate outcomes.

## Repro

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260616_008_form144_revision_readiness_blocker.py
```
