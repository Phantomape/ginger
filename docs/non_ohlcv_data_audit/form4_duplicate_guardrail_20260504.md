# Form 4 Overlay Guardrail Recheck

- experiment_id: `exp-20260504-003`
- timestamp: `2026-05-04T00:30:49Z`
- decision: `shadow_only_no_new_forward_evidence`
- production_impact: `data_audit_only_no_new_strategy_change`

## Hypothesis

Open-market insider buying may eventually confirm existing A/B candidates or seed
an external event queue, but the valid next step is not another static threshold
sweep. It is closed forward evidence from the default-off Form 4 queue.

## Historical Check

- `exp-20260503-048`: accepted-trade overlay overlap was too sparse: 0 matches
  inside 5/10/20 days, 2 inside 60 days, 5 inside 90 days.
- `exp-20260503-049`: top skipped-candidate overlap was 0/45 even with a
  120-calendar-day lookback.
- `exp-20260503-052`: large `meaningful_purchase_v1 >= $500k` purchases were
  shadow-promising as a standalone event source.
- `exp-20260503-053`: simple owner-role filters did not improve the branch
  enough to justify promotion.
- `exp-20260504-001`: the valid next step was implemented as a default-off
  forward observation queue that alters no orders.

This run does not repeat the rejected overlay joins or role/value sweeps.

## Data Availability / PIT Status

- Form 4 transaction file: `data/non_ohlcv/form4_transactions_20241002_20260502.jsonl`
- Rows written: `27,879`
- PIT-safe rows in backfill: `27,879`
- Form 4 filings seen: `6,558`
- Open-market purchase count: `131`
- Missing CIK ticker: `SNXX`
- Current queue smoke for `2026-05-04`: enabled `False`, candidate_count `0`,
  alters_orders `False`, data source loaded.

Historical rows are usable for shadow research with filing/usable-date fields,
but promotion still requires forward queue outcomes. There is no new closed
forward sample after `exp-20260504-001`.

## Shadow Metrics Carried Forward

Locked branch: `meaningful_purchase_v1` with total purchase value `>= $500k`.

| Horizon | Count | Avg Return | Median Return | Win Rate | Avg Excess vs SPY | Excess Win Rate |
|---|---:|---:|---:|---:|---:|---:|
| 5d | 13 | 2.67% | 2.52% | 76.92% | 1.96% | 69.23% |
| 10d | 13 | 6.10% | 5.53% | 84.62% | 4.76% | 84.62% |
| 20d | 13 | 6.58% | 3.56% | 69.23% | 5.02% | 69.23% |
| 60d | 12 | 14.51% | 10.71% | 66.67% | 10.79% | 58.33% |
| 90d | 11 | 18.92% | 14.42% | 63.64% | 10.87% | 54.55% |

10d by window:

| Window | Events | Valid 10d | Avg 10d Excess vs SPY |
|---|---:|---:|---:|
| late_strong | 4 | 4 | 4.84% |
| mid_weak | 10 | 8 | 5.27% |
| old_thin | 3 | 1 | 0.33% |

## Slot Value

Scarce-slot opportunity cost is not measurable yet. The queue has no current
candidate, and historical Form 4 events barely overlap accepted A/B entries or
top skipped opportunities. Early promotion could displace stronger A/B trades
without proven replacement value.

## Decision

`shadow_only_no_new_forward_evidence`. Keep Form 4 in the default-off forward
queue. Do not promote to production entries, ranking, sizing, add-ons, or exits.

## Next Minimum Action

Accumulate closed queue outcomes with frozen same-day alternatives. The next
valid promotion discussion needs forward replacement value, not another simple
purchase-value or owner-role sweep.
