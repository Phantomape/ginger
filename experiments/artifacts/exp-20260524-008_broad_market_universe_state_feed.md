# exp-20260524-008 Broad-Market Universe-State Feed

Decision: `accepted_measurement_repair_no_strategy_change`.

Single causal variable: derive a default-off broad-market paper feed from `universe_state` only when the static feed file is missing.

## Gate Summary

- Gate 1 baseline: EV `7.8941`, PnL `$234,850.99`.
- Gate 2: `True` across `11` open-position rows.
- Gate 3: no strategy filter added; survival unchanged.
- Gate 4: `False` because this is a no-orders measurement repair.

## Feed

- source: `data\daily\universe\universe_state_20260522.json`
- rule_version: `broad_market_universe_state_observation_feed_v1`
- ticker_count: `27`
- excluded_count: `15`
- sample: `AAOI, ASTS, BKSY, CEG, CIEN, CIFR, CORZ, CRWV, ETN, FN, GLW, GSAT, HAWK, IRDM, IREN`

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "default_off_paper_only": true,
  "parity_test_added": true,
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": true,
  "scope": "default_off_broad_market_forward_maturation_feed",
  "shared_policy_changed": true,
  "trade_enabled": false
}
```

No JavaScript was used.
