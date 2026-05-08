# SEC / Earnings / Filing Shock Audit - exp-20260508-002

## Decision

Decision: data_gap. The repo now has strong PIT timestamp and coverage scaffolding for SEC/earnings archives, but the directional financial shock fields needed for a tradable C-strategy grading harness remain sparse or semantic-only. No production path changed.

## Protocol

| Field | Value |
|---|---|
| mechanism_family | SEC/earnings filing-shock event confirmation overlay and C-strategy event grading |
| single_causal_variable | fresh PIT-safe SEC/earnings filing-shock field availability after exp-20260507-004 |
| mode | data audit plus prior shadow tag carry-forward |
| production_impact | replay_only=true; no signal, sizing, ranking, order, run, backtester, risk, or portfolio change |
| mechanism insight check | Does not retry raw SEC recency, filing-presence multipliers, OHLCV threshold sweeps, or C-sleeve reactivation |

## Historical Check

| Experiment | Result to preserve |
|---|---|
| exp-20260504-040 | Broad SEC/earnings family audited; only narrower governance/procedural branch stayed default-off candidate. |
| exp-20260504-046 | No fresh PIT-safe evidence after exp-044; data_gap. |
| exp-20260504-048 | No fresh evidence after exp-046; data_gap. |
| exp-20260507-003 | Recent filing presence/risk multiplier failed; do not retry raw recency. |
| exp-20260507-004 | Candidate filing-shock tags persisted; raw filing presence produced no B/C directional rows and negative slot value. |
| exp-20260507-011 | Re-enabling earnings_event_long regressed all windows; do not revive C solely from snapshots. |
| exp-20260507-020 | FD/Other 8.01 semantic branch was positive but immaterial; observe only. |

## Coverage Table

| Scope | Business days | Complete days | Complete fraction | Biased days | Notes |
|---|---:|---:|---:|---:|---|
| Fresh archive 2026-04-27 to 2026-05-05 | 7 | 7 | 1.0 | 0 | required artifacts present |
| Latest baseline non-OHLCV coverage 2024-10-02 to 2025-04-22 | 145 | 145 | 1.0 | 0 | decision=complete |

## Fresh Field Availability

| Source | Available | PIT status | Gap |
|---|---|---|---|
| SEC filing events 2026-05-06 | rows=67 | accepted/usable timestamps present in archive | metadata only without numeric shock direction |
| SEC filing text 2026-05-06 | rows=41 | accepted/usable timestamps present where SEC text row exists | text can support semantic buckets, not numeric EPS/revenue surprise |
| SEC filing features 2026-05-06 | rows=41, pit_safe=41 | PIT-safe rows available | same_accession_facts=0; companyfacts_path=None |
| Companyfacts backfill | rows=17689 | public-availability proxy | not same-accession joined in latest feature snapshot |
| Earnings snapshots | latest snapshot through 20260506 with exact coverage 1.0 | replayable repo snapshots | not vendor-grade consensus truth |
| Event snapshot 2026-05-06 | rows=7 | point_in_time_complete on rows | directional rows are semantic-derived and need forward outcomes |

Feature field counts from sec_filing_features_20260506:

| Field | Count |
|---|---:|
| gross_margin_delta | 0 |
| fcf_to_net_income_gap | 0 |
| inventory_growth | 0 |
| receivables_growth | 0 |

## Fresh Shadow Event Table

| Ticker | Event date | Usable trade date | Form | Accepted | Direction | Strength | Tag | Evidence |
|---|---|---|---|---|---|---|---|---|
| AMD | 20260506 | 2026-05-06 | 8-K | 2026-05-05T20:16:06 | unknown | low | D_unclear_or_missing_data | 8k_item_2_02 |
| APP | 20260506 |  | earnings |  | positive | high | A_no_recent_filing_event | earnings_beat |
| APP | 20260506 |  | 10-Q |  | unknown | low | D_unclear_or_missing_data | 10q |
| COIN | 20260506 | 2026-05-06 | 8-K | 2026-05-05T10:57:33 | unknown | low | D_unclear_or_missing_data | 8k_item_2_05 |
| DIS | 20260506 |  | earnings |  | positive | low | A_no_recent_filing_event | earnings_positive |
| LITE | 20260506 | 2026-05-06 | 8-K | 2026-05-05T20:11:28 | positive | medium | B_positive_filing_shock | margin_up |
| NVO | 20260506 |  | earnings |  | positive | unknown | A_no_recent_filing_event | earnings_positive |

## Baseline Metrics

| Scope | EV | Return % | PnL | Sharpe daily | Max DD % | Win % | Trades | Signals | Survival % | vs SPY pp | vs QQQ pp |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| latest baseline file | 0.3359 | 26.24 | 26242.68 | 1.28 | 9.05 | 40.91 | 22 | 60/55 | 91.67 | 32.97 | 33.73 |
| late_strong from exp-20260507-004 | 3.7435 | 83.56 | 83562.53 | 4.48 | 5.39 | 78.95 | 19 | 51/41 | 80.39 | 78.15 | 77.77 |
| mid_weak from exp-20260507-004 | 1.5478 | 57.54 | 57542.74 | 2.69 | 8.79 | 52.38 | 21 | 53/42 | 79.25 | 32.1 | 24.04 |
| old_thin from exp-20260507-004 | 0.3359 | 26.24 | 26242.68 | 1.28 | 9.05 | 40.91 | 22 | 60/55 | 91.67 | 32.97 | 33.73 |

## Shadow Returns Carried Forward

No new forward-return replay was run because the fresh 2026-05-06 tags have not matured. The prior candidate-level shadow result remains the controlling evidence.

| Tag | Candidates | 5d avg % | 10d avg % | 20d avg % | 60d avg % |
|---|---:|---:|---:|---:|---:|
| A_no_recent_filing_event | 67 | 0.4767 | 1.731 | 2.845 | 0.977 |
| B_positive_filing_shock | 0 | None | None | None | None |
| C_negative_filing_shock | 0 | None | None | None | None |
| D_unclear_or_missing_data | 71 | 0.8224 | 1.0909 | 2.8629 | 11.2336 |

## Candidate Overlap And Slot Value

candidate_count=138; selected_by_entry_plan_rows=113; selected_with_recent_filing=57.

Scarce-slot comparable count=16; 20d slot delta avg=-2.2776%, median=-1.8267%, win_rate=0.4375. This is not evidence for a filing-presence tie-breaker.

## Conclusion

Fresh PIT coverage supports continued shadow research, and the event snapshot now produces at least one semantic positive SEC row (LITE margin_up). That is still not enough to enter a default-off strategy harness because numeric shock fields, structured guidance, and matured forward returns are missing. Keep production unchanged.

Next minimal action: keep raw filing recency rejected; in shadow only, populate same-accession XBRL/companyfacts plus PIT consensus/guidance fields, then rerun candidate tagging after forward returns mature for the fresh 2026-05-06 semantic events.
