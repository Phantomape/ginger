# Full Candidate Filing-Shock Shadow Audit (exp-20260507-006)

## Decision
shadow_only

## Coverage
| window | complete_fraction | candidate rows | entered | recent filing rows | slot comparables |
|---|---:|---:|---:|---:|---:|
| late_strong | 1.0 | 41 | 20 | 19 | 3 |
| mid_weak | 1.0 | 42 | 21 | 21 | 1 |
| old_thin | 1.0 | 55 | 22 | 31 | 5 |

## Field Availability
{
  "sec_feature_rows": 8450,
  "pit_safe_rows": 8450,
  "pit_safe_fraction": 1.0,
  "directional_financial_shock_rows": 18,
  "field_availability_top": {
    "accepted_datetime:observed": 8450,
    "eps_surprise:missing_no_vendor_consensus": 8450,
    "guidance_raise_cut:missing_no_structured_guidance_source": 8450,
    "revenue_surprise:missing_no_vendor_consensus": 8450,
    "usable_trade_date:observed": 8450,
    "gross_margin_delta:missing": 8441,
    "fcf_to_net_income_gap:missing": 8432,
    "inventory_growth:missing": 8432,
    "receivables_growth:missing": 8432,
    "same_accession_facts:missing": 8425,
    "same_accession_facts:derived": 25,
    "fcf_to_net_income_gap:derived": 18,
    "inventory_growth:derived": 18,
    "receivables_growth:derived": 18,
    "gross_margin_delta:derived": 9
  },
  "gap_reasons_top": {
    "eps_and_revenue_surprise_require_pit_consensus_vendor": 8450,
    "guidance_raise_cut_requires_structured_guidance_source": 8450,
    "missing_same_accession_companyfacts": 8425
  }
}

## Production Impact
{
  "shared_policy_changed": false,
  "backtester_adapter_changed": true,
  "run_adapter_changed": false,
  "parity_test_added": false,
  "replay_only": true,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_candidate_ranking": false,
  "alters_sizing": false,
  "production_signal_path_changed": false
}

## Next Action
Fill directional same-accession/companyfacts or PIT consensus fields; full candidate persistence is now available for default-off replay.
