# SEC Same-Accession Candidate Touch Audit (exp-20260507-093)

## Hypothesis
Same-accession SEC Companyfacts may be absent from existing A/B candidate lookbacks; if so, filing-shock B/C cohort failure is a candidate-touch data gap rather than a classifier threshold problem.

## Decision
data_gap

## Aggregate
- candidate_count: `138`
- recent_filing_candidate_count: `71`
- recent_same_accession_candidate_count: `0`
- recent_directional_candidate_count: `0`
- feature_same_accession_rows: `25`
- feature_directional_rows: `18`
- B/C candidate counts: `0` / `0`

## Window Table
| window | candidates | recent filing | same-accession touch | directional touch | feature same-accession rows | feature directional rows | top failure reason |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | 41 | 19 | 0 | 0 | 16 | 9 | no_recent_filing_no_directional_event_for_ticker |
| mid_weak | 42 | 21 | 0 | 0 | 0 | 0 | no_recent_filing_no_directional_event_for_ticker |
| old_thin | 55 | 31 | 0 | 0 | 9 | 9 | no_recent_filing_no_directional_event_for_ticker |

## Interpretation
The repaired same-accession Companyfacts rows exist in the SEC feature table, but none are inside the 20-trading-day lookback of persisted A/B entry candidates. The current B/C cohort failure is therefore a candidate-touch/source-coverage gap, not evidence that a looser classifier should be promoted.

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
Do not loosen filing-shock classification yet. The next valid repair is a source/coverage step: collect same-day/same-accession earnings XBRL that actually touches A/B candidates, or add a PIT guidance/consensus source that can produce directional rows on candidate dates.
