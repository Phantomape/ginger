# exp-20260515-017 Sector ETF Candidate Pool

Decision: `rejected_sector_etf_candidate_pool`.

Single variable family: add one PIT-available sector/cross-asset ETF candidate at a time to the core universe, with a production-visible sector classification, while keeping the accepted signal/risk/sizing stack unchanged.

## Candidate Scout

| Ticker | Sector | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Trades | Max DD worse |
|---|---|:---:|---:|---:|---|---|---:|---:|
| XLE | Energy | FAIL | -1.1327 | $-25,529.75 | - | late_strong, mid_weak | 3 | +0.0142 |
| XLV | Healthcare | FAIL | -0.3045 | $-3,645.22 | - | late_strong | 1 | +0.0000 |
| XLP | Consumer Staples | FAIL | -1.1448 | $-23,734.29 | - | late_strong, old_thin | 1 | +0.0095 |
| XLU | Utilities | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| USO | Commodities | FAIL | -0.0909 | $-10,104.20 | late_strong | mid_weak, old_thin | 6 | +0.0018 |
| IEF | ETF | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |
| TLT | ETF | FAIL | -0.0301 | $-1,611.98 | - | mid_weak | 1 | +0.0000 |
| UUP | ETF | FAIL | +0.0000 | $+0.00 | - | - | 0 | +0.0000 |

Selected candidate: `XLU`.

## Selected Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Candidate trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.0322 | 5.0322 | +0.0000 | $114,886.19 | $114,886.19 | $+0.00 | 0.8039 | 0 |
| mid_weak | 1.9947 | 1.9947 | +0.0000 | $72,796.75 | $72,796.75 | $+0.00 | 0.7925 | 0 |
| old_thin | 0.5059 | 0.5059 | +0.0000 | $35,379.65 | $35,379.65 | $+0.00 | 0.9167 | 0 |

Production impact: rejected scout only; no shared policy, universe, or production adapter changed.
