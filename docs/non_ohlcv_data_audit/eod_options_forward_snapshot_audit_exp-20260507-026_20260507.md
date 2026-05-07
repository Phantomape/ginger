# exp-20260507-026 EOD Options Forward Snapshot Audit

Decision: `data_gap`
Run mode: data audit only; no production change.

## Hypothesis

Forward-daily EOD options structure snapshots may become a useful default-off
overlay for existing Ginger breakout/event candidates. The overlay should stay
non-standalone and should only tag existing candidates after PIT-safe coverage,
liquidity quality, and closed forward returns are available.

## Historical Check

Prior options work already exists. `exp-20260506-009` joined OnClickMedia
historical rows to 138 canonical-window candidate rows with 97.83% coverage,
but rejected promotion: call-structure support underperformed by -0.82pp on
20-day forward return, downside-risk tags were unstable across windows, and all
historical rows were PIT-unsafe because vendor-asof metadata was missing.

This run is not a repeat of the rejected call-OI / put-call / skew threshold
replay. The new evidence is forward-daily snapshot availability for 2026-05-05
and 2026-05-06.

## Data Availability

Forward snapshot files exist:

- `data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl`
- `data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl`

Coverage summary:

| Date | Ticker-date requests | Rows | PIT-safe rows | Errors | Liquidity-pass rows | Liquidity-pass rate | Tickers with >=10 liquid rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-05-05 | 48 | 4,767 | 4,767 | 0 | 1 | 0.02% | 0 |
| 2026-05-06 | 48 | 4,767 | 4,767 | 0 | 4,166 | 87.39% | 48 |

Raw schema fields are present for ticker, date, expiry, strike, call/put,
volume, open interest, bid, ask, mid, implied vol, delta, option liquidity
score, usable trade date, PIT flag, and retrieved_at. `vendor_asof` is missing
on all 9,534 rows; forward rows rely on `retrieved_at` plus conservative
next-weekday `usable_trade_date`.

The 2026-05-05 liquidity-pass collapse is a data-quality anomaly. Do not use
that day for alpha evidence until the score/feed issue is explained.

## Adjacent Data

Earnings snapshots exist, but the options rows are not yet joined into an
`earnings_iv_flag` or event-window replay table. True short-interest / borrow
pressure remains blocked; recent free-proxy audits rejected FINRA/FTD/Reg SHO
threshold variants as promotion evidence.

## Baseline Metrics

The production-equivalent strategy was unchanged. Latest canonical options
shadow baseline from `exp-20260506-009`:

| Window | EV | Return | SharpeD | Max DD | Win rate | Trades | Signals | Survived | Survival | vs SPY | vs QQQ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 3.4191 | 78.60% | 4.35 | 5.41% | 78.95% | 19 | 51 | 41 | 80.39% | 73.19pp | 72.80pp |
| mid_weak | 1.4415 | 55.02% | 2.62 | 8.79% | 52.38% | 21 | 53 | 42 | 79.25% | 29.58pp | 21.51pp |
| old_thin | 0.3179 | 24.64% | 1.29 | 8.05% | 40.91% | 22 | 60 | 55 | 91.67% | 31.37pp | 32.13pp |

Latest single-window checkpoint `data/backtest_results_20260507.json` stayed
unchanged at EV 0.3359, return 26.24%, SharpeD 1.28, max drawdown 9.05%, win
rate 40.91%, 22 trades, 60 generated, 55 survived, survival 91.67%, vs SPY
+32.97pp and vs QQQ +33.73pp.

## Shadow Status

Current forward snapshot overlay performance is not measurable yet:

- Forward 5/10/20/60d return: not closed.
- Future drawdown / realized vol: not closed.
- Candidate overlap: not measured against closed candidate outcomes; snapshots
  cover 48 universe tickers per day, not a completed candidate-outcome table.
- Scarce-slot value: not measurable forward yet.

Historical shadow reference from `exp-20260506-009` remains the only overlay
performance data and it is rejected for promotion:

| Tag | Aggregate 20d return delta | Slot conflict value 20d |
| --- | ---: | ---: |
| call_structure_support | -0.008225 | -0.113189 |
| downside_structure_risk | -0.037732 | -0.136492 |

## Decision

`data_gap`. The collection path is live, but the overlay is not a default-off
candidate yet. It needs enough forward PIT-safe days, closed outcomes, a stable
option-liquidity filter, and richer features such as IV rank, IV-vs-realized,
and earnings-IV context before another replay is justified.

## Next Minimum Action

Collect at least 10-20 forward snapshot days, fix or explain the 2026-05-05
liquidity anomaly, then compute closed 5/10/20d returns only for existing Ginger
candidates. Do not retry historical call/put/OI/skew threshold promotion on the
same PIT-unsafe rows.
