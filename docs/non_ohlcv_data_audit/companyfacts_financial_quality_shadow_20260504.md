# SEC Companyfacts financial-quality shadow replay

- Experiment: `exp-20260504-004`
- Status: `observed_only_not_promoted`
- Production impact: shadow-only; no strategy logic changed.

## Headline

The simple XBRL/companyfacts quality score is not promotion-quality: high-quality events are only mildly positive on aggregate and the warning-quality bucket performs as well or better, so the score is not a reliable monotonic ranking signal.

## Coverage

- Companyfacts accessions: `534`
- Financial filing events: `292`
- Price-covered events: `218`
- High-quality events: `135`
- High-quality valid 10d outcomes: `131`

## High Quality

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| high_quality | 135 | 0.45% | 48.09% | 1.66% | 48.06% |

## By Quality Bucket

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| high_quality | 135 | 0.45% | 48.09% | 1.66% | 48.06% |
| neutral_quality | 5 | -4.15% | 60.00% | -2.83% | 40.00% |
| positive_quality | 34 | -0.85% | 38.24% | -0.87% | 38.24% |
| warning_quality | 44 | 1.65% | 52.27% | 2.42% | 52.27% |

## By Window

| Cohort | Events | 10d excess avg | 10d win | 20d excess avg | 20d win |
|---|---:|---:|---:|---:|---:|
| late_strong | 75 | -0.06% | 44.59% | 1.60% | 41.10% |
| mid_weak | 71 | 0.12% | 52.17% | 1.06% | 52.94% |
| old_thin | 72 | 1.10% | 46.48% | 1.25% | 47.89% |

## Gate / Caveat

- Gate 4 is intentionally not passed because this is not a promoted strategy change.
- SEC Companyfacts `filed` date is a public-availability PIT proxy; it does not prove local production observation.
- This first score is deliberately simple; nearby point-weight tuning is not a valid next step.

## Next Action

Do not tune nearby point weights. A valid retry needs LLM filing-text grading, analyst revisions, or a cleaner same-quarter XBRL extraction for earnings releases.
