# Form 4 Current Snapshot Audit

- experiment_id: `exp-20260506-021`
- source: `data/non_ohlcv/form4_transactions_20260505.jsonl`
- decision: `shadow_only`
- production_impact: `shadow_audit_only_no_production_change`

## Hypothesis

Meaningful open-market insider buying may confirm existing `trend_long` and `breakout_long` candidates, especially CEO/CFO large buys, cluster buys, first buys, or post-drawdown buys. This run only audits the latest PIT-safe daily Form 4 snapshot and the existing default-off paper sleeve.

## Historical Check

This direction has already been studied. The relevant history is:

- `exp-20260503-017`: initial Form 4 audit was a data gap before transaction XML existed.
- `exp-20260503-052`: standalone meaningful-purchase sleeve was shadow-promising but not promoted.
- `exp-20260504-001`: default-off Form 4 forward event queue was accepted for observation.
- `exp-20260504-034`: Form 4 satellite overlay was positive but below materiality.
- `exp-20260505-010`: simple sale-pressure de-risk was rejected.
- `exp-20260505-023`: 20260504 current snapshot had zero meaningful purchase candidates.

This run is not a repeat of the sale-pressure branch and does not retune thresholds. It checks the newer `20260505` snapshot that arrived after the prior current-snapshot audit.

## Coverage

- Form 4 rows: `573`
- PIT-safe rows: `573`
- filings seen: `122`
- documents fetched/read: `122`
- open-market purchase rows: `4`
- meaningful purchase rows >= $500k: `0`
- option-exercise rows: `164`
- 10b5-1 rows: `238`
- external issuer rows excluded: `24`
- transaction code counts: `A=39`, `C=22`, `F=42`, `G=2`, `M=122`, `P=4`, `S=342`

CIK mapping is adequate for this audit:

- core: `43/45`, missing `IWM`, `SNXX`
- pilot: `3/3`
- observation: `16/16`

## PIT Status

The snapshot is PIT-safe for forward observation because rows include `accepted_at`, `usable_trade_date`, and `pit_safe_flag`. This run does not use the current snapshot to make a historical performance claim.

## Field Availability

Available fields include ticker, cik, accession number, accepted timestamp, transaction date, officer title, owner role flags, transaction code, shares, price, value, direct/indirect ownership, ownership nature, 10b5-1 flag, option-exercise flag, open-market-purchase flag, usable trade date, and PIT flag.

The only relevant missing join for the requested scoring packet is `market_cap`, so `insider_buy_value_to_market_cap` remains blocked.

## Raw Purchases

The four raw open-market purchase rows are all below the existing meaningful threshold:

- `TSM`: 3 VP purchase rows, total value `$7,760`, max row `$3,860`
- `CAT`: 1 director purchase row, total value `$219,210`

These are valid Form 4 purchase rows but are intentionally excluded as tiny/sub-threshold for alpha claims.

## Shadow Metrics

- candidate_count: `0`
- latest signal file: `data/quant_signals_20260505.json`
- latest signal count: `0`
- signals with meaningful insider buy: `0`
- signals without meaningful insider buy: `0`
- meaningful insider buy but no signal: `0`
- raw sub-threshold purchase issuers without signal: `TSM`, `CAT`
- overlap with existing signals: `0`
- scarce-slot opportunity cost: not measurable
- forward 5/10/20/60/90d returns: not measurable, zero tagged candidates

The default-off Form 4 paper sleeve also has zero candidates, zero pending entries, zero open positions, and zero closed positions through the latest `2026-05-05` snapshot.

## Decision

`shadow_only`. The data path is now usable for forward observation, but this snapshot adds no actionable meaningful-purchase candidate and no slot-value evidence. Do not promote, retune thresholds, or connect this to production entries.

## Next Minimum Action

Keep the default-off Form 4 forward queue running. Revisit only after nonzero meaningful-purchase candidates and closed paper outcomes exist, or after a richer ex-ante discriminator is available without changing the production signal path.
