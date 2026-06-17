# exp-20260617-003 Post-CCC Non-Repeat Alpha Surface

Status: `blocked`
Decision: `blocked_no_gate4_ready_nonrepeat_alpha_surface_after_ccc_zero_sample`

## Hypothesis

candidate_pool/data-edge: after CCC produced zero target trades, the only credible next alpha needs new PIT evidence such as analyst revision breadth/dispersion, structured customer/supplier economics, independent listing/lockup/float data, or mature closed forward rows.

## Gate 1-4

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | 0.8039 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,110.11 | $+0.00 | 0.7925 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | 0.8667 |

- Aggregate EV delta: `+0.0000`
- Aggregate PnL delta: `$+0.00`
- Gate 4 status: `blocked_no_gate4_ready_nonrepeat_alpha_surface`
- Failed/blocking reasons: `missing_revision_breadth, missing_structured_event_tuple_fields, missing_listing_lockup_float, accepted_or_rejected_near_neighbors_frozen, forward_replacement_rows_insufficient_or_frozen`

## Candidate Readiness

| Candidate | Decision | Reason |
|---|---|---|
| `analyst_revision_breadth_dispersion` | `blocked_missing_historical_fields` | Historical snapshots still lack analyst count, revenue estimate, dispersion, fiscal-period, and vendor-asof fields. |
| `structured_customer_supplier_contract_economics` | `blocked_missing_structured_tuple_and_recent_sparse_failure` | Structured tuple fields are absent in sampled PIT surfaces, and the latest named-counterparty replay had only one target trade. |
| `independent_seasoned_listing_lockup_float` | `blocked_missing_listing_lockup_float_surface` | No true listing date, lockup expiration, or float-asof fields are available locally; first-seen OHLCV would be a frozen proxy. |
| `companyfacts_quality_or_working_capital_retry` | `blocked_frozen_near_neighbor_or_zero_sample` | SBC is already accepted and adjacent retunes are frozen; working capital/quality variants either failed window/comparator gates or the CCC bundle generated zero target trades. |
| `ohlcv_relation_or_price_only_retry` | `blocked_accepted_or_frozen_without_new_field` | The warehouse is OHLCV-only and accepted relation/macro/compression helpers already have shared parity; new price-only variations need materially independent forward evidence. |

## Data Surface

- Warehouse conclusion: `warehouse_is_ohlcv_only_for_alpha_surface`
- Missing revision fields: `analyst_count_current_qtr, analyst_count_next_qtr, revenue_estimate_current_qtr, revenue_estimate_next_qtr, estimate_dispersion, vendor_asof, fiscal_period`
- Missing structured-event fields: `actor, object, relation, magnitude, size_usd, source_id, evidence_span, provenance_hash`
- Missing listing/lockup/float fields: `listing_date, ipo_date, de_spac_date, lockup_expiration_date, public_float, float_asof`
- Forward replacement rows are not a new Gate-4-ready surface: `Rows are concentrated in already accepted/frozen surfaces such as low_deployment_etf, state_surface, event sleeves, or existing helpers; new non-repeat candidate pools lack 20+ closed replacement rows.`

## Production Impact

No strategy, helper, runner, ranking, sizing, exit, watchlist, LLM/news, or order path changed. Any future positive alpha from these directions must use one shared default-off helper across historical replay and daily production observation before retention.

## Reflection

The attempted second alpha lane is blocked because the local PIT surfaces do not expose the independent fields required by the strongest non-repeat ideas, while nearby executable variants are already accepted/frozen or recently rejected.

No JavaScript was used.
