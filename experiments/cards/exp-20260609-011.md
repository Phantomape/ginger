# exp-20260609-011: Revision Surprise Low-Extension Shared Adapter

- decision: `accepted_shared_default_off_revision_surprise_low_extension_adapter`
- aggregate EV: `7.8941` -> `8.0787` (+0.1846)
- aggregate PnL delta: `$+2,893.75`
- target trades: `31`
- max single positive share: `0.415681`
- positive PnL HHI: `0.244677`
- Gate 1 docs-baseline match: `True`
- failed gates: `none`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3088 | +0.1460 | $+1,425.44 | 7 |
| mid_weak | 2.1402 | 2.1591 | +0.0189 | $+689.36 | 15 |
| old_thin | 0.5911 | 0.6108 | +0.0197 | $+778.95 | 9 |

## Conclusion

Numeric Gate 4 passed and the policy now uses the same shared helper for historical replay and daily default-off paper snapshots. It is accepted only as default-off paper observation; trade_enabled remains false until forward rows and PIT source provenance pass.

The rule uses only same-day OHLCV and prior 20-day OHLCV context known at the signal close. It is replay-only/default-off, so no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|
| MU | 3 | $1,493.15 | 0.415681 |
| DDOG | 2 | $647.12 | 0.180153 |
| LLY | 2 | $606.53 | 0.168853 |
| GE | 1 | $275.76 | 0.076769 |
| NFLX | 1 | $154.62 | 0.043045 |
| BKNG | 1 | $146.70 | 0.04084 |
| DIS | 2 | $91.57 | 0.025492 |
| JPM | 1 | $85.56 | 0.023819 |
| MA | 2 | $46.21 | 0.012864 |
| AAPL | 2 | $39.47 | 0.010988 |

## Shared Adapter

- helper: `quant/revision_surprise_low_extension_paper_sleeve.py`
- daily snapshot API: `build_revision_surprise_low_extension_snapshot`
- historical replay API: `build_revision_surprise_low_extension_candidate_rows`
- production parity: default-off paper only; no run.py/order/ranking/sizing/exit change.
- live limitation: EPS estimate provenance remains proxy-grade pending PIT source evidence.
