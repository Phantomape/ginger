# exp-20260715-008 — Execution-date cash-constrained core order admission

**Lane**: measurement_repair · **Decision**: accepted_measurement_repair (conditional keep) · **Owner**: claude-cash-ledger

## Defect

The canonical core backtester (`quant/backtester.py`) booked entry and add-on
fills with no execution-date cash constraint. Position sizing caps each fill
against marked portfolio value, but nothing checked settled cash, so
overlapping fills routinely exceeded fundable capital. `exp-20260715-005`'s
closed-rows reconstruction first quantified the phenomenon (18-20
negative-cash events per canonical window, ~-$23k max); this experiment's
inline ledger — which also sees add-ons and partial reduces — shows the true
depth: peak overdrafts of **-$166,598 / -$188,621 / -$188,512** on $100,000
initial capital. The published champion booked up to ~$189k more entry basis
than its settled cash could fund, i.e. roughly half its PnL was physically
unexecutable in a no-leverage cash account.

## Repair

Cash ledger inside `BacktestEngine.run()` behind `CASH_LEDGER_ENFORCED`
(default `False` — every existing baseline stays byte-identical, following the
`LIQUIDITY_AWARE_SLIPPAGE` precedent):

- Core entry: debit booked (rounded) entry price × shares at fill date. When
  enforced, unaffordable orders are deterministically scaled to
  `floor(cash / booked_price)` and skipped when that is zero, with a logged
  `insufficient_cash` entry decision.
- Add-on: debit the booked basis delta post re-averaging; enforced add-ons cap
  at affordable shares or skip (`skipped_insufficient_cash`).
- Partial reduce / daily exit / force close: credit average-cost basis plus
  realized pnl (= net proceeds after round-trip cost). Core-sleeve gated; pilot
  sleeves never touch the ledger.
- `result["cash_ledger"]` reports enforcement flag, min cash + date, negative
  cash events, scaled/skipped admission events, ending cash, and an exact
  conservation check (`ending_cash == initial + realized core pnl`, unrounded
  accumulator).

## Evidence (exp-20260712-015 frozen inputs, three canonical windows)

All machine acceptance checks passed
(`data/experiments/exp-20260715-008/exp_20260715_008_cash_constrained_core_admission.json`):

- **Gate 1 identity**: audit-only pass reproduced the published post-MTM
  baseline exactly (trade-row and daily-return-series hashes, EV, PnL, trade
  counts, all three windows).
- **Zero negative-cash events** in all enforced windows; min cash $0-$12.
- **Exact cash conservation** in every window and mode (error 0.0).
- **Overdraft reproduced** independently in every audit-only window (17-18
  events each).

Honest re-measurement under enforcement:

| Window | EV | PnL | Max DD | Trades | Survival | Scaled / skipped entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 7.2115 → 4.1067 | $117,073 → $70,075 | 5.94% → **3.94%** | 18 → 13 | 80.4% → 88.9% | 7 / 10 |
| mid_weak | 3.7446 → 1.9908 | $77,846 → $51,976 | 5.02% → 6.61% | 21 → 13 | 78.9% → 81.2% | 5 / 18 |
| old_thin | 1.3137 → 0.1082 | $42,934 → $8,941 | 9.75% → **8.89%** | 23 → 23 | 90.3% → 92.3% | 9 / 7 |

Aggregate EV 12.2698 → **6.2057** (-49.4%); aggregate PnL $237,852 →
**$130,992** (-$106,860). Drawdown improves in 2 of 3 windows (less hidden
leverage); survival improves in all 3. These deltas are the honest
re-measurement of the same policy, not a strategy regression.

## Production impact

None at default. `CASH_LEDGER_ENFORCED` stays `False`; live/default orders,
ranking, sizing, and exits unchanged. The audit block in every backtest result
is additive.

## Implications (for the follow-up re-baseline decision)

1. Unenforced canonical EV/PnL are leverage-inflated upper bounds. The Gate-4
   ratchet has been comparing challengers against a champion funded by
   impossible cash.
2. Capital-allocation / displacement comparisons versus the unenforced
   champion (e.g. exp-20260715-002's opportunity-cost panel, exp-20260715-005's
   ETF-on-remaining-cash test) are biased against the challenger: the "10% of
   the active core" they had to beat partially does not exist in cash terms.
3. Follow-up (new ticket, explicit decision): flip the default, republish a
   post-cash-ledger Gate-1 anchor (exp-20260712-015-style frozen-input
   capture), and revisit the parked portfolio/ETF lanes whose reopen
   conditions reference executable-cash accounting.
4. exp-20260715-005's named reopen condition ("shared core allocator with
   actual execution-date cash reservations … deterministic scaling or
   rejection of unaffordable core orders") is now implemented in the shared
   engine.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260715_008_cash_constrained_core_admission.py
.\.venv\Scripts\python.exe -m pytest quant\test_backtester_cash_ledger.py -q
```

Changed files: `quant/backtester.py`, `quant/test_backtester_cash_ledger.py`,
`quant/experiments/exp_20260715_008_cash_constrained_core_admission.py`,
`docs/backtesting.md`, ticket/card/manifest/log for exp-20260715-008.
