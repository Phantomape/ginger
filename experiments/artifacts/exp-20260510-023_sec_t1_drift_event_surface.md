# exp-20260510-023 SEC T+1 Drift Event Surface

Decision: `observed_only_paper_watch_candidate`

## Aggregate

- shadow candidates: `393`
- valid 10d forward candidates: `363`
- positive 10d avg windows: `2/3`
- aggregate 10d avg return: `0.012219`
- aggregate 10d win rate: `0.5179`
- platform-pool candidates: `67`

## Window Detail

### late_strong

- SEC rows: `311`
- positive T+1 excess candidates: `147`
- 10d avg return: `0.006284`
- 10d win rate: `0.4242`
- coverage complete fraction: `1.0`

### mid_weak

- SEC rows: `269`
- positive T+1 excess candidates: `130`
- 10d avg return: `0.030976`
- 10d win rate: `0.6667`
- coverage complete fraction: `1.0`

### old_thin

- SEC rows: `274`
- positive T+1 excess candidates: `116`
- 10d avg return: `-0.001002`
- 10d win rate: `0.4685`
- coverage complete fraction: `1.0`

## Notes

- Shadow-only audit; no production orders, sizing, ranking, LLM, exits, or slots changed.
- Uses SEC accepted_at / usable_trade_date as a public PIT proxy; it does not prove the historical production process observed each filing.
