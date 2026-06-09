# exp-20260609-015: Persistent Revision Surprise Overlay

- decision: `rejected_persistent_revision_surprise_overlay`
- aggregate EV: `7.8941` -> `7.8941` (+0.0000)
- aggregate PnL delta: `$+0.00`
- target trades: `0`
- max single positive share: `None`
- positive PnL HHI: `None`
- Gate 1 docs-baseline match: `True`
- failed gates: `accepted_adapter_aggregate_ev_not_beaten, accepted_adapter_aggregate_pnl_not_beaten, aggregate_ev_not_positive, aggregate_pnl_not_positive, late_strong_ev_below_accepted_adapter, late_strong_pnl_below_accepted_adapter, mid_weak_ev_below_accepted_adapter, mid_weak_pnl_below_accepted_adapter, old_thin_ev_below_accepted_adapter, old_thin_pnl_below_accepted_adapter, target_concentration_failed, target_sample_too_small, target_window_coverage_too_small, window_ev_regression`

## Three-Window Result

| window | EV before | EV after | EV delta | PnL delta | target trades |
|---|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $+0.00 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $+0.00 | 0 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $+0.00 | 0 |

## Conclusion

The 7d/30d persistent revision overlay did not show replacement value over the accepted revision+surprise+low-extension adapter. No production or shared policy behavior is retained.

The rule uses only same-day OHLCV and prior 20-day OHLCV context known at the signal close. It is replay-only/default-off, so no production entry, ranking, sizing, exit, LLM/news, watchlist, or order behavior changed.

## Top Positive Contributors

| ticker | trades | paper PnL | positive PnL share |
|---|---:|---:|---:|

## Persistent Revision Overlay

- source: existing `estimate_revision_ledger_YYYYMMDD.jsonl` rows
- rule: `pit_safe_flag && estimate_revision_usable && eps_estimate_delta_7d > 0 && eps_estimate_delta_30d > 0`
- policy: accepted helper selected top1 only; no backup substitution.
- production parity: replay-only and rejected unless it beats the accepted shared helper; no production/default path changed.

## Accepted Comparator Gate

- comparator: `data/experiments/exp-20260609-011/revision_surprise_low_extension_shared_adapter.json`
- aggregate EV delta vs accepted: `-0.1846`
- aggregate PnL delta vs accepted: `-2893.75`
- failed comparator reasons: `accepted_adapter_aggregate_ev_not_beaten, accepted_adapter_aggregate_pnl_not_beaten, late_strong_ev_below_accepted_adapter, late_strong_pnl_below_accepted_adapter, mid_weak_ev_below_accepted_adapter, mid_weak_pnl_below_accepted_adapter, old_thin_ev_below_accepted_adapter, old_thin_pnl_below_accepted_adapter`
