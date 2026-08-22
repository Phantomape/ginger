# exp-20260728-008 — Massive dividend declaration research surface

## Disposition

Accepted as an alpha-enabling measurement repair only. This experiment did
not read a forward return, change a strategy, enable a paper sleeve, or touch
production orders. The dividend-restart hypothesis remains a `research_pit`
lead with an `observed_only` result ceiling.

## Frozen source contract

- Source: authorized `GET /stocks/v1/dividends` on `api.massive.com`, under the
  existing local-use entitlement attestation in
  `experiments/artifacts/exp-20260728-002_massive_source_contract.md`.
- The live endpoint rejected both declaration-date server filters and an
  explicit declaration-date sort with HTTP 400 before any page was written.
  A one-row zero-persistence probe proved the accepted contract is the
  documented default ticker/ascending order with `limit=5000`; later pages
  follow the provider's opaque cursor.
- The complete provider history is retained because filtering on the later
  ex-dividend date would make source inclusion depend on a post-declaration
  field. The decision-safe projection applies the predeclared local
  declaration range `2021-01-01..2026-05-31` instead.
- Frozen snapshot: 144 pages, 716,736 provider rows, all-pages SHA-256
  `6cada394b8c4e90fff58c24c16c950edc139da94d00ca4ce6db9ce0f0c170630`.
- Decision-range projection: 237,247 provider rows and 137,435 positive-USD
  ticker-date groups before the frozen restart/identity/liquidity rules.

Every page stores the exact gzip-compressed response, response hash,
sanitized URL, normalized rows, page record, and checkpoint atomically. The
strong verifier replays every raw page and compares every normalized row.
A completed rerun with a client that throws on any network call returned the
same hash with `resumed_without_network=true`.

`distribution_type`, `frequency`, `split_adjusted_cash_amount`, and
`historical_adjustment_factor` remain raw provenance only. They are absent
from normalized decision columns and the decision-safe projection. Cash
amounts use canonical decimal `TEXT`; ticker case is preserved.

## Outcome-blind readiness

The frozen treatment is one ticker-date decision for a positive USD cash
declaration after at least 1,095 days without a prior same-ticker positive USD
declaration, active-common-stock membership from the latest verified as-of
snapshot no later than the declaration, at least 20 predecision bars, close
at least $3, trailing-20 median dollar volume at least $1 million, and top two
per declaration day by liquidity.

| Window | Eligible before top-2 | Selected unique ticker-date touches |
|---|---:|---:|
| old_thin | 41 | 40 |
| mid_weak | 22 | 22 |
| late_strong | 33 | 32 |

All windows pass the predeclared minimum of five touches. Five provider rows
were collapsed at the ticker-date decision level; no exact economic-effect
duplicate was found. The audit read only bars with
`trade_date <= declaration_date`; it read no H10 bar, forward return, or
outcome field.

## Synthesis and next action

- Cross-sectional opportunity-cost winner remains cash / no new core entry.
- Selected mechanism: a long distribution interruption followed by a
  positive cash declaration may reveal restored cash-generation confidence
  and capital-return capacity.
- A later outcome-aware test, if authorized after D0-D3 and model-diverse
  debate, is frozen to next regular-session open through H10 close after cost.
  Its primary replacement comparator is the same-date cash-feasible core
  candidate or cash; SPY and QQQ are secondary comparators.
- Falsifier: any window below five decisions, or a separately authorized
  replay that fails the replacement comparator after costs.
- Do not reserve another ID for dividend pagination, storage, query-shape
  retuning, or routine rematerialization. The only valid next alpha action is
  outcome-blind D0-D3 plus model-diverse debate, followed—only if promoted—by
  one separate `private_replay_scout` with `observed_only` ceiling.

## Verification

- `quant/test_massive_ohlcv_backfill.py`: 56 passed.
- Massive fingerprint regressions: 12 passed.
- Gate-1 baseline, `quant/run.py`, `quant/backtester.py`,
  `operator_inputs/open_positions.json`, and `data/live_pilot/` hashes were
  identical before and after.
- Readiness artifact:
  `data/alpha_search/massive_dividend_declaration_readiness_20260728.json`
  (SHA-256
  `656064b54c04c775c819fe6209cc353e492a2473c90f496b5e4f67000ca73916`).
