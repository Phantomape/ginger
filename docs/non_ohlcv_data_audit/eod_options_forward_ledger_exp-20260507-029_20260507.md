# EOD options forward ledger audit (exp-20260507-029)

## Hypothesis

Forward PIT-safe EOD options structure tags may enrich existing Ginger candidates as a default-off overlay, but they must not create standalone entries or touch production ranking/sizing.

## Historical check

Checked AGENTS.md, docs/alpha-optimization-playbook.md, docs/experiment_log.jsonl, docs/experiments/logs, and universe-scout automation memory. Prior options work (`exp-20260506-009`) rejected naive historical options overlay promotion because historical rows lacked vendor_asof and tag performance was unstable. This run is not a retry of those thresholds; it adds a forward-only candidate-tag ledger and quarantines bad daily snapshots.

## Source and PIT status

- Source: OnClickMedia EOD option-chain snapshots.
- Local chain files: data/non_ohlcv/options_onclickmedia_chain_20260505.jsonl, data/non_ohlcv/options_onclickmedia_chain_20260506.jsonl.
- PIT stance: forward-collected rows are only usable from each row's `usable_trade_date`; `vendor_asof` is still unavailable.
- Production impact: none; script/artifacts only.

## Liquidity audit

| quote_date | rows | liquidity pass rows | pass rate | bid>0 | ask>bid | mid>0 | OI>0 | delta nonzero | liquid tickers >=10 rows | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-05-05 | 4767 | 1 | 0.00021 | 1 | 1 | 1 | 1 | 1 | 0 | quarantine_recommended |
| 2026-05-06 | 4767 | 4166 | 0.873925 | 4543 | 4766 | 4766 | 4679 | 2442 | 48 | ok |

5/5 is not a missing-data problem; it is a vendor/collection quality anomaly where volume and IV exist, but bid/ask/mid/OI/delta are zero for nearly every row. Treat that day as quarantined unless a refreshed source snapshot replaces it.

## Candidate tag ledger

- Candidate count: 7.
- Options-covered candidates: 7 (1.0).
- Option-liquidity-eligible candidates: 3.
- PIT-join-safe candidates: 0 (0.0).
- Squeeze tags: 0.
- Downside-risk tags: 0.
- Earnings-vol tags: 0 (not wired until PIT earnings-date join exists).
- Forward 5/10/20/60d returns: pending; no current OHLCV snapshot covers post-2026-05-06 outcomes.

## Decision

`shadow_only`. Keep collecting forward PIT-safe rows and do not use 2026-05-05 for scoring. Promotion would require nonzero candidate overlap where options are usable before candidate action date, closed forward returns, and positive slot conflict value versus existing signals.
