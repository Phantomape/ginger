# Frozen plan: broad OHLCV warehouse intraday-bar contamination repair + completed-session write guard

Captured 2026-09-25 before reservation. Outcome-blind: only bar identity/price fields and ledger identity counts were read; no PnL or outcome fields.

## Defect (identity evidence)
- Hot warehouse tier data/warehouse/warehouse_main_hot.sqlite holds 6583 rows for sessions 2026-09-15, 09-16, 09-17, 09-18, 09-21 whose updated_at precedes the session close (written 16:55Z-19:13Z by mid-session run.py passes started 09:02-11:07 local; sources ohlcv_warehouse_refresh:yfinance 1304/1304/1304/1304/1251, run.py:cached_extra 12/day, run.py:primary_batch 56 on 09-21).
- refresh_warehouse_ohlcv fetches with end=now and upserts with update_existing=False, so an intraday snapshot bar (partial-session close/high/low/volume) is frozen forever; the evening pass cannot correct it. Close gap vs massive daily_bars > 0.3%: 846/1309, 1132/1309, 848/1309, 893/1309, 711/1309 on those five sessions vs 0/1309 on 09-23.
- Session 2026-09-22: yfinance served no bar on the 09-22 evening pass (7 inserts) and only 110 more on 09-23; 1162 tickers have 09-21 and 09-23 but no 09-22. yfinance serves 09-22 now (sampled ADI/DIS/ROKU/AXP), so daily 30d re-fetches self-heal this hole; it is included in the repair set only to stop the consumer starvation one day earlier.
- Consumer effect already observed: exp-20260913-007 leg priceability excluded 57/59 long and 31/32 short tickers on the 09-24 batch and 22/28 long on the 09-23 batch (baskets admitted with 2/1 and 6/3 tickers); news_event_exposure_observer h10 alignment returns None for every ticker lacking 09-22 (rows stay pending). Settled outcomes that read the five contaminated closes (entity_theme forward observer 415 rows with exit_date in the window; exposure observer 359 closed rows with entry 09-01..09-21, subset affected) are append-only and are NOT rewritten here.

## Single causal variable
Bars for a session that has not completed (latest_completed_us_equity_session at the run clock, 16:15 New York) must never be written by refresh_warehouse_ohlcv; the already-written intraday rows for the five sessions are re-fetched from the same authorized vendor path and rewritten once under a distinct source label.

## Steps
1. Code: refresh_warehouse_ohlcv gains run_clock (timezone-aware, default now UTC); each fetched frame is truncated to dates <= latest_completed_us_equity_session(run_clock) before the split guard and upsert; summary records dropped_incomplete_session_rows and completed_session. New unit test: fetcher returns a frame ending on the run date; at 10:00 New York the run-date row is not inserted, at 16:30 it is.
2. Data repair (one-off, this ID): for every (ticker, date) in the frozen before-census set plus the 1162 hole tickers on 09-22, fetch via data_layer.get_ohlcv_many (same vendor path as the daily refresh, lookback 20d), slice each frame to exactly those dates, upsert into the hot tier with update_existing=True and source ohlcv_warehouse_refresh:yfinance:intraday_bar_repair:<experiment_id>. No other (ticker, date) row is written. Rows for sessions after latest_completed_us_equity_session(now) are never written.
3. After census with the same script: intraday_written_rows_total for the five sessions -> 0 expected (rewritten rows carry a new updated_at); close gap vs massive on those sessions -> comparable to 09-23 (0 or dividend-adjustment residue); 09-22 rows -> 158 + up to 1162.
4. Tests: quant/test_ohlcv_warehouse_refresh.py (new test) and quant/test_ohlcv_warehouse.py.

## Acceptance
Accepted only if the new test passes, existing refresh/warehouse tests pass, the after census shows 0 intraday-written rows on the five sessions, at most 5% of compared tickers with >0.3% close gap vs massive on each of the five sessions, and no row outside the frozen set changed (row count per session unchanged except 09-22 inserts). No sleeve rule, holding period, cost, or acceptance contract changes; no basket re-admitted; no settled outcome rewritten.

## Not in scope / user decisions
- Re-settlement of outcomes already closed against the five contaminated sessions (append-only ledgers; needs its own registered decision).
- Identifying the launcher of the mid-session run.py passes (not a Claude scheduled task, not a Windows scheduled task visible to this account); the guard makes the write path safe regardless.
