# exp-20260721-003 — S&P Composite 1500 addition preflight

## Decision

`rejected_before_price_read`

The fixed shared-paper-first lead was stopped before Gate 2-4 and before any
entry/exit return or PnL read.  The corrected outcome-blind preflight failed
the preregistered sector-concentration ceiling in `mid_weak`, and the official
S&P Global website terms do not provide authorization to use the website
content to develop or support an investment strategy.

No shared observer, daily wiring, paper ledger, ranking, sizing, exit, live
order, or `trade_enabled` default was added.

## Locked causal policy used for the preflight

- Admit only true net-new S&P Composite 1500 entrants.  Exclude an addition
  when the same publication date, effective date, and ticker also has a
  deletion from the S&P 500, MidCap 400, or SmallCap 600, including when the
  two rows are split across release URLs.  That is a tier migration rather
  than net new tracker demand for the Composite 1500.
- Treat a date-only release as known at end of day.  The prospective lifecycle
  would enter at the first regular-session open strictly after publication and
  exit at the last close strictly before the effective date.
- Merge all releases with the same publication calendar date into one
  independent event clock.
- Compute inverse-volatility concentration weights from exactly 20
  close-to-close log returns strictly before publication.  Missing or invalid
  risk history fails closed.
- Preflight thresholds in every standard window: at least 5 independent
  announcement dates, at least 10 eligible tickers, and top sector weight no
  greater than 35%.

## Preliminary outcome-blind results

These aggregate counts came from the first causal correction, which removed
tier migrations found within one release table.  The subsequent code review
showed that an economic event can be split across release URLs, so the final
offline parser now pairs additions/deletions across URLs by publication date,
effective date, and ticker.  The source terms prevented re-reading the source
to recompute the table under that stricter rule.  These counts therefore record
the preliminary failure but are not a canonical PIT dataset or Gate input.

| Window | All additions | Tier migrations excluded | Net new | Eligible | Clocks | Tickers | Top sector weight | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `old_thin` 2024-10-02..2025-04-22 | 65 | 29 | 36 | 33 | 21 | 33 | 26.84% | pass |
| `mid_weak` 2025-04-23..2025-10-22 | 43 | 13 | 30 | 29 | 20 | 29 | **36.93%** | **fail** |
| `late_strong` 2025-10-23..2026-04-21 | 88 | 41 | 47 | 43 | 17 | 43 | 20.79% | pass |

The first loose row count overstated the causal sample because it included
S&P 500/400/600 tier migrations.  The preliminary correction and locked
inverse-volatility weighting exposed a `mid_weak` concentration failure.  A
sector cap, threshold relaxation, equal-dollar substitution, or outcome-based
subtype filter would be an unregistered retune and was not run.  The source
authorization failure is independently decisive.

## Source and authorization boundary

- Public release archive inspected: <https://press.spglobal.com/>
- S&P Global terms inspected: <https://www.spglobal.com/en/terms-of-use>
- The terms limit the license to personal, internal, non-commercial use and
  expressly prohibit using website content to develop or support an investment
  strategy unless another agreement grants permission.
- The archive supplies only a publication date in the inspected historical
  view; it does not establish an exact release timestamp or immutable initial
  vintage.  A local manifest date is therefore an unverified audit input, not
  proof that the event clock is PIT-valid.
- No source HTML or row-level S&P content is persisted or redistributed in this
  repository.  The repository retains only this minimal rejection audit and an
  offline parser/preflight harness for synthetic or separately authorized local
  inputs.

## Evidence and production status

- `candidate_entry_exit_or_forward_return_read`: `false`.
- `post_manifest_date_price_or_return_data_read`: `false`.
- `post_publication_price_or_return_data_read`: `unknown`, because the local
  manifest date is not independently proven to be the true publication clock.
- `gate2_to_gate4_run`: `false`.
- `accepted_alpha`: `false`.
- `source_contract_authorized_for_investment_strategy`: `false`.
- Active baseline remains
  `data/backtests/backtest_results_warehouse_snapshot_standard_windows_cash_feasible_20260715.json`
  with SHA-256
  `4e9ef413126c947b9712fd0879b83c74160f787898860987d204bfc9d60f7731`.

## Reflection and reopen rule

Do not retry this archive/policy on the frozen windows by adding a sector cap,
changing the 35% threshold, changing inverse-volatility to equal-dollar, or
including tier migrations.  This surface is parked.  Reopen requires explicit
written permission or another authorized immutable constituent-change source,
plus a genuinely new evidence axis under the repository novelty rules; the
same rows with a retuned response are insufficient.
