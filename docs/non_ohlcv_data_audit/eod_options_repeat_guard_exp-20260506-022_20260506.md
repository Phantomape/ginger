# EOD Options Structure Overlay Repeat Guard - exp-20260506-022

## Decision

`data_gap`. Do not promote the EOD options overlay and do not rerun another naive historical replay yet.

## Hypothesis

EOD options IV, skew, term structure, OI concentration, and put/call structure may improve Ginger only as an overlay for existing breakout, short-pressure, or earnings-event candidates. It should not create standalone entries.

## Historical Check

Prior options work already exists:

- `exp-20260505-021`: no local options-market structure data existed.
- `exp-20260506-003`: OnClickMedia default-off adapter and daily collection were added.
- `exp-20260506-009`: canonical-window shadow overlay covered 135/138 candidate days, but historical rows were PIT-unsafe and overlay evidence was unstable.

Recent playbook guidance says not to repeat naive call OI, put OI, call-dominance, or put-skew rules without new PIT-safe evidence, richer IV/earnings/short-linked features, and slot replacement value.

## Data Availability

Available:

- Adapter: `quant/options_onclickmedia.py`
- Shadow runner: `scripts/run_options_overlay_shadow.py`
- Current forward summary: `data/non_ohlcv/options_onclickmedia_summary_20260505.json`
- Historical shadow report: `data/experiments/exp-20260506-009/options_overlay_shadow_report.json`

Available chain fields include ticker, date, expiry, strike, call/put, volume, open interest, bid, ask, mid, implied vol, delta, option liquidity score, usable trade date, and PIT flag.

Missing or not promoted:

- IV rank
- IV percentile
- IV minus realized volatility
- earnings IV flag
- vendor as-of timestamp
- ticker-level option liquidity filter
- closed forward outcomes for current PIT-safe rows
- true short-interest or borrow linkage

## PIT Status

Historical OnClickMedia rows from `exp-20260506-009` are not decision-grade because they lack vendor-as-of metadata. They remain useful only for shadow diagnostics.

The current `2026-05-05` forward snapshot is PIT-safe for forward observation:

- rows written: 4,767
- PIT-safe rows: 4,767
- PIT-unsafe rows: 0
- ticker-date requests: 48
- errors: 0
- option-liquidity-pass rows: 1
- option-liquidity-pass rate: 0.0002

This is not enough for a new replay because no 5/10/20/60d outcomes have closed.

## Prior Shadow Overlay Evidence

`exp-20260506-009` covered 138 existing candidate days and 13,484 option rows.

All candidates:

- 5d average forward return: 0.010061
- 10d average forward return: 0.017511
- 20d average forward return: 0.032044
- 60d average forward return: 0.066281
- 20d average future drawdown: -0.060482
- 20d average realized vol: 0.361229

`call_structure_support`:

- count: 75
- 20d average return: 0.016569
- 20d return versus no-call bucket: -0.008225
- window deltas: late_strong -0.021347, mid_weak +0.076930, old_thin -0.057693

`downside_structure_risk`:

- count: 31
- 20d average return: -0.008001
- 20d return versus no-downside bucket: -0.037732
- window deltas: late_strong -0.094107, mid_weak -0.120848, old_thin +0.061721

## Candidate Overlap And Slot Value

The options overlay was tested only on existing Ginger candidates.

- standalone options entries: 0
- entered candidates: 62
- skipped candidates: 76
- options-covered entered candidates: 61
- options-covered skipped candidates: 74
- call-structure slot conflicts: 12
- average call-structure slot conflict value, 20d: -0.113189
- downside-risk slot conflicts: 5
- average downside-risk slot conflict value, 20d: -0.136492

## Production Impact

No production path changed.

- shared policy changed: false
- backtester adapter changed: false
- run adapter changed: false
- production signal path changed: false
- production orders changed: false
- parity test added: false
- replay only: true

## Next Minimum Action

Keep daily forward options collection running. Revisit only after at least 5 to 10 PIT-safe snapshot days exist and enough tagged option-liquid candidates have closed 5/10/20/60d outcomes. The next valid test should add richer IV rank, IV-vs-realized, earnings-IV, and short/borrow-linked tags before considering any default-off replay.
