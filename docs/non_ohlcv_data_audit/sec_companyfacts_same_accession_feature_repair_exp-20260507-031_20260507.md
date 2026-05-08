# SEC Companyfacts Same-Accession Feature Repair (exp-20260507-031)

## Hypothesis
Directional SEC filing-shock fields can be repaired without vendor data if the existing PIT companyfacts selected JSONL is auto-discovered and joined by same accession during non-OHLCV backfill.

## Result
Decision: `shadow_only`.

The data gap is partially repaired: same-accession Companyfacts rows now derive nonzero financial-shock fields where public SEC Companyfacts has matching accession rows.

## Coverage / Field Table
| window | rows | same_accession_rows | directional_rows | gross_margin_delta | fcf_to_net_income_gap | inventory_growth | receivables_growth |
|---|---:|---:|---:|---:|---:|---:|---:|
| smoke | 222 | 0 | 0 | 0 | 0 | 0 | 0 |
| late_strong | 2766 | 16 | 9 | 0 | 9 | 9 | 9 |
| mid_weak | 2465 | 0 | 0 | 0 | 0 | 0 | 0 |
| old_thin | 2304 | 9 | 9 | 9 | 9 | 9 | 9 |

## Shadow Audit
Full-candidate rerun field availability: `{"sec_feature_rows": 8450, "pit_safe_rows": 8450, "pit_safe_fraction": 1.0, "directional_financial_shock_rows": 18, "field_availability_top": {"accepted_datetime:observed": 8450, "eps_surprise:missing_no_vendor_consensus": 8450, "guidance_raise_cut:missing_no_structured_guidance_source": 8450, "revenue_surprise:missing_no_vendor_consensus": 8450, "usable_trade_date:observed": 8450, "gross_margin_delta:missing": 8441, "fcf_to_net_income_gap:missing": 8432, "inventory_growth:missing": 8432, "receivables_growth:missing": 8432, "same_accession_facts:missing": 8425, "same_accession_facts:derived": 25, "fcf_to_net_income_gap:derived": 18, "inventory_growth:derived": 18, "receivables_growth:derived": 18, "gross_margin_delta:derived": 9}, "gap_reasons_top": {"eps_and_revenue_surprise_require_pit_consensus_vendor": 8450, "guidance_raise_cut_requires_structured_guidance_source": 8450, "missing_same_accession_companyfacts": 8425}}`

B/C candidate cohorts remain empty under the conservative classifier; current directional rows are sparse, mixed, or do not touch candidates.

## PIT Caveat
SEC filing tradability still uses accepted_datetime -> usable_trade_date. Companyfacts filed date is only a public-availability proxy and does not prove local production observed the fact intraday.

## Production Impact
{
  "shared_policy_changed": false,
  "backtester_adapter_changed": false,
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
Improve event-quality classification or source coverage: prioritize same-accession 10-Q/10-K candidate touches, structured guidance raise/cut, or PIT consensus EPS/revenue surprise before another production alpha attempt.
