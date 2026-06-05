# exp-20260605-007 Broad 1446-Universe SEC Companyfacts Realized-Fundamentals Asset

Decision: `accepted_broad_universe_companyfacts_data_asset`.

Read-only `measurement_repair` (data asset build). Motivated by the
eps_estimate data-quality audit: yfinance `eps_estimate` covers only ~50
curated names (≈0 on the broad universe) and is annual/quarterly
contaminated (`forwardEps` stored as if quarterly in
`data_layer._populate_from_info`). SEC Companyfacts realized fundamentals
are free, official, PIT-safe (filing date), and — confirmed here — cover
the broad universe richly. This builds the broad asset the existing
`FUNDAMENTAL_GROWTH_RS` line only runs on ~40 names. Changes no entries,
exits, ranking, sizing, paper sleeves, or orders.

## What was built

For the 1,446 `all_windows_full_liquid` tickers in the `exp-20260519-030`
warehouse: fetch each CIK's SEC Companyfacts (cached, SEC-compliant
0.11s/request), map us-gaap concepts to canonical revenue / eps_basic /
eps_diluted / net_income facts, and derive PIT-safe YoY growth rows
(`kova_data_sidecar.derive_companyfacts_growth_rows`, which drops any fact
with `filed > asof`).

- Dataset: `data/kova/fundamentals/companyfacts_growth_broad_universe_20260604.jsonl`
  (~124 MB, **199,887 growth rows**; `growth_status == "ok"` for 137,642,
  `missing_prior_period` for 62,245). Gitignored (regenerable); the audit
  is the committed evidence.
- Audit: `data/experiments/exp-20260605-007/broad_universe_companyfacts_coverage_audit.json`.
- Fetch: 867s (~14.5 min), 6 errors (all ETFs / a CIK edge case).

## Coverage of the 1,446 universe (as of 2026-06-04)

| Metric | Count | Share |
|---|---|---|
| With a CIK | 1,446 | 100% |
| With any fundamental facts | 1,281 | 88.6% |
| With revenue facts | 1,170 | 80.9% |
| With EPS facts | 1,221 | 84.4% |
| **With clean OK revenue YoY growth** | **1,146** | **79.3%** |
| **With clean OK EPS YoY growth** | **1,213** | **83.9%** |
| No usable fundamentals | 165 | 11.4% |

Canonical growth rows: net_income 71,600 · revenue 45,138 · eps_basic
41,732 · eps_diluted 41,417.

### The ~11% gap is structural and expected

- **Foreign filers / ADRs** that file 20-F in IFRS taxonomy (no us-gaap
  XBRL): AZN, ASML, BABA, BIDU, BILI, BEKE, BP, BHP, BTI, BUD, ARM, BNTX,
  AEG, AEM, AGI, AU, BCS, BMO, BNS, CM, … (the no-usable list is almost
  entirely non-US-GAAP issuers).
- **Index ETFs** (no fundamentals by definition): SPY, QQQ, DIA, MDY (the
  6 fetch 404s).

So among genuine US-GAAP filers the coverage is effectively near-complete;
79–84% of the whole 1,446 (incl. ADRs/ETFs) carry clean YoY growth.

## vs yfinance eps_estimate

| | yfinance eps_estimate | SEC Companyfacts (this asset) |
|---|---|---|
| Broad-universe coverage | ~0 (≈50 curated only) | 79–84% with clean YoY growth |
| Quality | annual/quarterly contaminated; unreliable actual | XBRL as-filed |
| PIT | backfilled (midnight-timestamp) history | genuine filing-date PIT |
| Construct | forward estimate | realized actuals + growth |
| Cost | free but dirty | free, official |

Caveat: Companyfacts is **realized** fundamentals, not forward estimates,
so it complements rather than replaces an estimate-revision signal. But it
is the clean, broad, free fundamental-quality/growth surface the repo's
strongest accepted lead (`FUNDAMENTAL_GROWTH_RS`) already exploits on the
curated 40 — now available for the full 1,446.

## PIT / rebuild

- PIT-safe: consume only rows with `asof_date <= signal_date`
  (`derive_companyfacts_growth_rows` already enforces `filed <= asof`).
- Rebuild (free official SEC API, cached under `data/cache/sec/companyfacts/`):
  `.\.venv\Scripts\python.exe quant\experiments\exp_20260605_007_broad_universe_companyfacts_asset.py`

## Documentation

Integrated into `docs/data_inventory.md`: two Canonical Map rows (curated +
broad) and a "Broad-Universe Realized Fundamentals" subsection with the
coverage, PIT semantics, and rebuild command.

## Files

- `quant/experiments/exp_20260605_007_broad_universe_companyfacts_asset.py` (new, driver)
- `data/experiments/exp-20260605-007/broad_universe_companyfacts_coverage_audit.json` (new, audit evidence)
- `data/kova/fundamentals/companyfacts_growth_broad_universe_20260604.jsonl` (124 MB, gitignored, regenerable)
- `docs/data_inventory.md` (updated)
- `experiments/logs/exp-20260605-007.json`, `experiments/tickets/exp-20260605-007.json`

No JavaScript was used.
