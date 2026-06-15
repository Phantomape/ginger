# exp-20260615-007 Gross-Margin RS Allocator Source-Extension Blocker

- Decision: `blocked_duplicate_prior_gross_margin_allocator_source_extension`
- Strategy behavior changed: `false`
- No JavaScript was used.

## Duplicate Evidence

- Prior artifact: `data/experiments/exp-20260610-019/exp_20260610_019_fundamental_growth_rs_allocator_source_extension.json`
- Prior decision: `rejected_fundamental_growth_rs_allocator_source_extension`
- Fundamental source rows by window: `{'late_strong': 154, 'mid_weak': 386, 'old_thin': 331}`
- Selected FGRS rows by window: `{'late_strong': 8, 'mid_weak': 11, 'old_thin': 14}`
- Selected rows with gross-margin pass: `{'late_strong': 8, 'mid_weak': 11, 'old_thin': 14}`

Example selected rows:

| Window | Ticker | Signal Date | Gross Margin Pass | Gross Rule | Source Rank |
|---|---|---:|---|---|---:|
| late_strong | CRDO | 2025-10-24 | True | gross_margin_quality_candidate_source_v1 | 8 |
| mid_weak | PLTR | 2025-04-23 | True | gross_margin_quality_candidate_source_v1 | 8 |
| old_thin | APP | 2024-10-15 | True | gross_margin_quality_candidate_source_v1 | 8 |

## Gate 1-4

- Gate 1: canonical baseline from `docs/backtesting.md`, aggregate EV `7.8941`, aggregate PnL `$234850.99`.
- Gate 2: no executable rows created; future alpha still requires `entry_date` and `target_price`.
- Gate 3: no filter added; baseline min survival `0.7925`.
- Gate 4: before/after identical across `late_strong`, `mid_weak`, and `old_thin`; launch blocked.

## Conclusion

The strongest apparent alpha was not new: exp-20260610-019 already admitted current gross-margin-enabled Fundamental Growth RS rows into the allocator and rejected it versus the accepted allocator comparator.

Best next direction: New free-data edge: PIT estimate breadth/dispersion/provenance, customer/supplier relation evidence, or forward closed rows from accepted default-off adapters.
