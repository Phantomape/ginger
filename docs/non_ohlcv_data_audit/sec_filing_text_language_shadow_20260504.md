# SEC filing-text language shadow replay

- Experiment: `exp-20260504-007`
- Status: `observed_only_not_promoted`
- Production impact: shadow-only; no strategy logic changed.

## Headline

The fixed filing-text language proxy did not clear a promotion-quality bar. Use the text layer as structured LLM input, not as a standalone keyword strategy.

## Coverage

- Text rows: `306`
- Text status counts: `{'ok': 306}`
- Evaluated events: `302`
- Price-covered events: `232`
- Earnings positive-language events: `65`
- Earnings positive valid 10d outcomes: `62`

## Primary Cohort

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| earnings_positive_language | 65 | -1.27% | 40.32% | -0.32% | 45.16% |

## By Language Bucket

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| deferred_or_operational | 7 | -0.73% | 42.86% | -1.97% | 50.00% |
| negative_language | 32 | 3.22% | 58.62% | 4.93% | 65.52% |
| neutral_or_mixed_language | 123 | 1.19% | 49.14% | 1.47% | 43.97% |
| positive_language | 70 | -1.19% | 42.42% | -0.33% | 45.45% |

## By Text Event Type

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| deferred_results_or_operational_update | 7 | -0.73% | 42.86% | -1.97% | 50.00% |
| earnings_release_text | 152 | 1.03% | 48.23% | 2.00% | 50.35% |
| item_2_02_other_text | 73 | 0.11% | 48.57% | 0.14% | 41.43% |

## By Window

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| late_strong | 78 | 0.29% | 41.89% | 0.60% | 34.25% |
| mid_weak | 74 | 1.22% | 51.47% | 2.12% | 58.21% |
| old_thin | 80 | 0.57% | 51.32% | 1.31% | 50.67% |

## Gate / Caveat

- Gate 4 is intentionally not passed because this is not a promoted strategy change.
- SEC archive text is public-PIT keyed by accepted_at/usable_trade_date, but the fetch happened after the fact.
- This is a fixed keyword proxy, not an LLM grade; use it as a baseline and packet schema.

## Next Action

Do not tune nearby keyword lists. A valid retry should use LLM filing-text grading on the frozen packets or join analyst revisions to these same SEC results events.
