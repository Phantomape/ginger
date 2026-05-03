# Form 4 Insider Overlay No-New-Data Recheck

- Experiment: exp-20260503-037
- Run time: 2026-05-03T15:05:02+00:00
- Decision: data_gap
- Production impact: data_audit_only; no run/backtester/signal/risk/portfolio path changed.

## Hypothesis

Meaningful open-market insider buying, especially CEO/CFO buys, cluster buys, first purchases, or post-drawdown buys, may confirm existing trend_long / breakout_long candidates. This run does not test production behavior; it only checks whether new PIT-safe Form 4 transaction evidence exists after exp-20260503-033.

## Historical Check

Exact prior Form 4 audits already exist: exp-20260503-017, exp-20260503-020, exp-20260503-025, exp-20260503-026, exp-20260503-030, and exp-20260503-033. They all found the same blocker: CIK mapping is mostly present, but transaction-level, PIT-safe Form 4 rows are absent.

The playbook still ranks Insider/Form 4 as a valid external event-confirmation source, but only as a shadow/default-off overlay until PIT transaction rows exist. This recheck therefore does not rerun the zero-row shadow overlay.

## Data Availability

- SEC / CIK infrastructure: present via quant/sec_ticker_map.py, quant/sec_submissions.py, and data/sec_company_tickers.json.
- Existing Form 4 audit script: quant/experiments/exp_20260503_017_form4_insider_overlay_audit.py.
- Default-off transaction adapter: missing.
- Current archived news Form 4 items: 0.
- Current news source diagnostics: 8-K, 10-Q, and 10-K only; no Form 4 source.
- SEC submissions cache Form 4 metadata rows: 34,738, including 72 current-universe metadata rows.
- PIT status of submissions cache: biased static snapshot, useful only for existence diagnostics.

## CIK Mapping Gap

- Core universe: 43/45 mapped; missing IWM and SNXX.
- Pilot universe: 3/3 mapped.
- Observation universe: 13/13 mapped.
- Interpretation: CIK mapping is not the blocking gap. Missing transaction XML fields are the blocker.

## Required Fields

Available locally: ticker, cik, accession_number, filing_datetime.

Missing locally: transaction_date, officer_title, is_director, is_officer, is_10pct_owner, transaction_code, shares, price, transaction_value, direct_or_indirect, ownership_nature, 10b5_1_flag, option_exercise_flag, open_market_purchase_flag, usable_trade_date, pit_safe_flag.

Because those fields are missing, open-market purchases cannot be separated from sales, option exercises, gifts, 10b5-1 activity, or tiny non-informative transactions.

## Shadow Overlay Metrics

- Meaningful insider-buy candidate count: 0.
- Signals with meaningful insider buy: 0.
- Signals without insider buy: 0 because no Form 4 tag table exists.
- Insider buy but no signal: 0.
- Forward 5/10/20/60/90d return of tagged candidates: not measurable.
- Candidate overlap with existing signals: 0.
- Scarce-slot opportunity cost: not measurable.

## Decision

Decision remains data_gap. Do not promote a Form 4 overlay, do not add a production filter, and do not infer slot value from static filing metadata.

## Next Minimum Action

Build a default-off append-only Form 4 adapter that archives SEC owner=include type=4 feeds and transaction XML fields with usable_trade_date and pit_safe. Rerun shadow tagging only after nonzero PIT-safe open-market purchase rows accumulate.
