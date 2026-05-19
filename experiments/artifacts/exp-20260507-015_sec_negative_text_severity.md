# exp-20260507-015 SEC Negative Text Severity

Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, event notional, capacity, holding period, and production orders are unchanged.

## Hypothesis

Within the frozen SEC negative-reaction event sleeve, severe negative filing text may indicate real business deterioration rather than temporary overreaction; excluding that subset may improve satellite event alpha.

## Three-window comparison

| Window | Core EV | Full bundle EV | Severity-gated EV | Delta vs full | Core PnL | Full PnL | Severity PnL | Removed trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 3.7435 | 4.2452 | 4.2409 | -0.0043 | $83,562.53 | $90,131.87 | $90,039.68 | 1 |
| mid_weak | 1.5478 | 2.0019 | 1.9975 | -0.0044 | $57,542.74 | $65,850.51 | $65,706.28 | 1 |
| old_thin | 0.3359 | 0.3676 | 0.3623 | -0.0053 | $26,242.68 | $27,641.23 | $27,447.60 | 2 |

## Decision

Rejected: severe negative SEC filing text did not improve the full event bundle. Do not retry simple language_score/negative_phrase_hits exclusion gates on this frozen sample; the evidence says the market-reaction event packet is stronger than this text-severity subfilter.

## Removed Trades

```json
{
  "late_strong": [
    {
      "entry_date": "2025-11-07",
      "exit_date": "2025-11-20",
      "language_score": -9,
      "negative_phrase_hits": 12,
      "net_return_pct": 0.009219,
      "pnl": 92.19,
      "reaction_excess_return": -0.010121,
      "source": "sec_negative_reaction",
      "ticker": "MCD"
    }
  ],
  "mid_weak": [
    {
      "entry_date": "2025-05-05",
      "exit_date": "2025-05-16",
      "language_score": -17,
      "negative_phrase_hits": 20,
      "net_return_pct": 0.014423,
      "pnl": 144.23,
      "reaction_excess_return": -0.008666,
      "source": "sec_negative_reaction",
      "ticker": "MCD"
    }
  ],
  "old_thin": [
    {
      "entry_date": "2024-10-31",
      "exit_date": "2024-11-13",
      "language_score": -17,
      "negative_phrase_hits": 20,
      "net_return_pct": 0.013951,
      "pnl": 139.51,
      "reaction_excess_return": -0.007917,
      "source": "sec_negative_reaction",
      "ticker": "MCD"
    },
    {
      "entry_date": "2025-01-30",
      "exit_date": "2025-02-12",
      "language_score": -2,
      "negative_phrase_hits": 14,
      "net_return_pct": 0.005413,
      "pnl": 54.13,
      "reaction_excess_return": -0.014654,
      "source": "sec_negative_reaction",
      "ticker": "RTX"
    }
  ]
}
```
