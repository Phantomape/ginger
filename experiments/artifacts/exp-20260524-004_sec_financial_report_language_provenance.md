# exp-20260524-004 - SEC Financial-Report Language Provenance

## Decision

Accepted as `measurement_repair`. This does not change entries, exits,
filters, ranking, sizing, risk allocation, LLM behavior, or production orders.

## AGENTS Gate Questions

1. Alpha hypothesis: SEC fact/tone and guidance-language buckets may separate
   durable post-report drift from noisy T+1 reactions.
2. Prior experiments: `exp-20260520-034` was blocked because frozen SEC rows
   lacked `language_bucket` and phrase-hit provenance; recent core scalar
   attempts failed Gate 4 and were not retried here.
3. Single causal variable: add production-visible language provenance to the
   default-off financial-report T+1 queue.
4. Acceptance standard: queue and production wrapper expose accession-matched
   language fields, tests pass, and production impact remains observe-only.
5. Reproducibility: rerun the focused pytest command and this experiment script.

## Change

`quant/sec_event_queue.py` now joins SEC financial-report event rows to
`sec_filing_text` rows by `(ticker, accession_number)` with an accession-only
fallback. Covered candidates carry:

- `language_bucket`
- `language_score`
- positive/negative phrase hits
- guidance raise/cut hits
- `text_event_type`
- `sec_text_coverage_status`
- `language_feature_rule_version`

`quant/run.py` passes the daily `sec_filing_text` path into the financial-report
T+1 queue builder.

## Probe

- candidate_count: 1
- text_status: loaded
- loaded_text_row_count: 1
- language_covered_count: 1
- candidate_language_bucket: `positive_language`
- candidate_text_event_type: `earnings_release_text`

## Verification

- passed: quant/sec_event_queue.py quant/run.py
- passed: 34 tests in quant/test_sec_event_queue.py and quant/test_sec_financial_report_event_sleeve.py

## Production Status

Production now emits the same text-derived provenance that the paper sleeve's
fact/tone attribution expects. The queue remains default-off and `trade_enabled`
stays false; no order, ranking, or sizing behavior changed.
