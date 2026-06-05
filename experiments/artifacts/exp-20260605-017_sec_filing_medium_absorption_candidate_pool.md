# exp-20260605-017 SEC Filing Medium Absorption Candidate Pool

- Decision: `rejected_preflight_data_limited`
- Lane: `alpha_search`
- Changed variable: `sec_filing_medium_credibility_absorption_candidate_source_v1`
- Result: not run through Gate 4 because the required historical field was unavailable.

## Preflight

The reserved hypothesis required `source_credibility_bucket=medium` in SEC filing feature rows across the canonical three windows. A read-only scan of `data/non_ohlcv/sec_filing_features_*.jsonl` found 951 unique PIT-safe 8-K feature rows across the three windows, but `source_credibility_bucket`, `low_volume_predictability_bucket`, `predictability_mosaic_bucket`, and `text_direction_vs_price_bucket` were all missing in those historical rows. The field exists only in newer forward files, so this hypothesis cannot be evaluated under `docs/backtesting.md` three-window rules.

## Production Boundary

No production adapter, `run.py`, `backtester.py`, ranking, sizing, exits, LLM/news path, watchlist, or order path changed. No JavaScript was used.

## Next

Use a historically available SEC feature relation instead of retuning this missing field.
