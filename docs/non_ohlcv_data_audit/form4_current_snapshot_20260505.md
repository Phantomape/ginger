# Form 4 Current Snapshot Audit - 2026-05-05

Experiment: `exp-20260505-023`

## Hypothesis

Public-market insider Form 4 buying may be useful as a positive confirmation tag for existing `trend_long` / `breakout_long` candidates. This run does not test a new entry, risk rule, threshold, or production path. It only audits whether the latest PIT-safe Form 4 transaction snapshot contains actionable meaningful purchase evidence.

## Historical Check

This Form 4 family has already been tested several times:

- `exp-20260503-017`: initial Form 4 audit found CIK mapping was mostly usable, but no PIT-safe transaction-level archive was available at that point.
- `exp-20260503-052`: standalone meaningful-purchase event sleeve was promising but not promoted.
- `exp-20260503-053`: owner-role discriminator was rejected.
- `exp-20260504-001`: default-off forward observation queue was accepted without core strategy changes.
- `exp-20260504-006`: slot replacement value was inconclusive.
- `exp-20260504-009`: event-sleeve replay was positive but stayed default-off.
- `exp-20260504-034`: Form 4 satellite overlay was positive but not material enough for promotion.
- `exp-20260505-010`: simple sale-pressure de-risk was rejected.

Playbook guardrail: do not retune Form 4 purchase thresholds, owner roles, holding periods, capacity, or live promotion on the same frozen sample. A valid next step needs closed forward paper evidence or a materially richer discriminator.

## Data Availability

Latest source: `data/non_ohlcv/form4_transactions_20260504.jsonl`

Snapshot status:

- Snapshot as-of date: `2026-05-04`
- Snapshot generated: `2026-05-05T06:38:14+00:00`
- Date range: `2026-04-24` to `2026-05-04`
- Tickers requested: 52
- Tickers mapped to CIK: 51
- Missing CIK: `SNXX`
- Filings seen: 103
- Documents fetched or read: 103
- Transaction rows written: 549
- PIT-safe rows: 549
- Open-market purchase rows: 3
- Meaningful purchase rows above $500k: 0
- Option exercise rows: 62
- 10b5-1 flagged rows: 195
- Excluded external-issuer rows: 30

Required Form 4 overlay fields are now mostly present at transaction level: `ticker`, `cik`, `accession_number`, `accepted_at`, `transaction_date`, `officer_title`, `is_director`, `is_officer`, `is_10pct_owner`, `transaction_code`, `shares`, `price`, `transaction_value`, `direct_or_indirect`, `ownership_nature`, `10b5_1_flag`, `option_exercise_flag`, `open_market_purchase_flag`, `usable_trade_date`, and `pit_safe_flag`.

The three open-market purchases are all tiny TSM rows with total transaction value of $7,760 and usable trade date `2026-04-30`. They are correctly excluded by the existing meaningful-purchase rule.

## Shadow Overlay Metrics

Meaningful insider-buy definition for this audit: `open_market_purchase_flag=true`, `option_exercise_flag=false`, `pit_safe_flag=true`, and purchase value above the existing meaningful threshold.

- `candidate_count`: 0
- `signals_with_meaningful_insider_buy`: 0
- `signals_without_insider_buy`: not recomputed; no candidate tag exists
- `insider_buy_but_no_signal`: 0
- `overlap_with_existing_signals`: 0
- `scarce_slot_conflict_count`: 0
- `scarce_slot_opportunity_cost`: not measurable
- `forward_5d_return_of_tagged_candidates`: no tagged candidates
- `forward_10d_return_of_tagged_candidates`: no tagged candidates
- `forward_20d_return_of_tagged_candidates`: no tagged candidates
- `forward_60d_return_of_tagged_candidates`: no tagged candidates
- `forward_90d_return_of_tagged_candidates`: no tagged candidates

The default-off forward sleeve is also empty:

- `candidate_count`: 0
- `pending_count`: 0
- `open_position_count`: 0
- `closed_position_count`: 0
- `realized_pnl_to_date`: 0
- `trade_enabled`: false

## Baseline Metrics

No backtest was rerun because this is a data audit with no strategy, ranking, sizing, universe, or production-order change. The canonical accepted core metrics remain unchanged:

| Window | EV | Return | PnL | Sharpe daily | Max DD | Win rate | Trades | Generated | Survived | Survival | vs SPY | vs QQQ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `late_strong` | 3.4191 | 78.60% | 78600.33 | 4.35 | 5.41% | 78.95% | 19 | 51 | 41 | 80.39% | 73.19% | 72.80% |
| `mid_weak` | 1.4415 | 55.02% | 55015.08 | 2.62 | 8.79% | 52.38% | 21 | 53 | 42 | 79.25% | 29.58% | 21.51% |
| `old_thin` | 0.3179 | 24.64% | 24642.07 | 1.29 | 8.05% | 40.91% | 22 | 60 | 55 | 91.67% | 31.37% | 32.13% |

Expected value score delta: `0.0`.

## Decision

Decision: `shadow_only`

Form 4 remains a plausible non-OHLCV event-confirmation family, and the current adapter now provides PIT-safe transaction rows. This specific snapshot does not contain actionable meaningful open-market purchase candidates, does not overlap existing signals, and does not create measurable scarce-slot value.

Production impact: `shadow_audit_only_no_production_change`. No core modules, thresholds, universe files, rankings, sizing rules, backtester logic, or production order paths were changed.

Next minimal action: continue the existing default-off Form 4 forward queue and wait for nonzero meaningful purchase candidates plus closed paper outcomes before any new replay or promotion attempt. Do not retune purchase thresholds or owner-role filters on this zero-candidate snapshot.
