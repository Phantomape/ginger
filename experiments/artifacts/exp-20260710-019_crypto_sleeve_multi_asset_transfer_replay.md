# exp-20260710-019: Crypto Sleeve Multi-Asset Transfer Replay

- Status: `observed_only_rejected_crypto_sleeve_multi_asset_transfer_replay`
- Decision: `observed_only_rejected_crypto_sleeve_multi_asset_transfer_replay`
- Acceptance rule: Observed-only positive lead only if the unchanged shared crypto policy beats fee-aware buy-and-hold EV in at least 2 of 3 windows for a majority of fetched non-BTC assets, improves drawdown for every evaluated asset, and aggregate cross-asset policy return is positive; no production behavior changes.
- Runner: `.\.venv\Scripts\python.exe -B quant\experiments\exp_20260710_019_crypto_sleeve_multi_asset_transfer_replay.py`

## Asset Results

| Asset | Fetched | Pass | EV win windows | DD win windows | Aggregate policy/B&H return | Failed checks |
|---|---|---:|---|---|---:|---|
| ETH-USD | yes | False | crypto_bear_2021_2022 | crypto_bear_2021_2022,current_cycle_2025_2026 | -0.634923 / -0.413605 | ev_beats_buy_hold_in_2_of_3_windows;drawdown_below_buy_hold_in_all_windows;aggregate_policy_total_return_positive |
| SOL-USD | yes | False | crypto_bear_2021_2022 | crypto_bear_2021_2022,current_cycle_2025_2026 | 1.125107 / 0.560606 | ev_beats_buy_hold_in_2_of_3_windows;drawdown_below_buy_hold_in_all_windows |
| XRP-USD | yes | False | crypto_bear_2021_2022,current_cycle_2025_2026 | crypto_bear_2021_2022,current_cycle_2025_2026 | -0.898336 / -0.344429 | drawdown_below_buy_hold_in_all_windows;aggregate_policy_total_return_positive |
| ADA-USD | yes | False | none | crypto_bear_2021_2022,post_bear_recovery_2023_2024,current_cycle_2025_2026 | 0.116785 / -0.878156 | ev_beats_buy_hold_in_2_of_3_windows |
| BNB-USD | yes | False | crypto_bear_2021_2022,current_cycle_2025_2026 | post_bear_recovery_2023_2024,current_cycle_2025_2026 | -0.439572 / -0.091101 | drawdown_below_buy_hold_in_all_windows;aggregate_policy_total_return_positive |
| DOGE-USD | yes | False | crypto_bear_2021_2022 | crypto_bear_2021_2022,post_bear_recovery_2023_2024,current_cycle_2025_2026 | -0.776604 / -0.816448 | ev_beats_buy_hold_in_2_of_3_windows;aggregate_policy_total_return_positive |
| LTC-USD | yes | False | crypto_bear_2021_2022,post_bear_recovery_2023_2024 | crypto_bear_2021_2022,current_cycle_2025_2026 | -0.838022 / -0.843473 | drawdown_below_buy_hold_in_all_windows;aggregate_policy_total_return_positive |
| LINK-USD | yes | False | crypto_bear_2021_2022 | crypto_bear_2021_2022,post_bear_recovery_2023_2024,current_cycle_2025_2026 | -0.702953 / -0.813827 | ev_beats_buy_hold_in_2_of_3_windows;aggregate_policy_total_return_positive |

## Batch Gate

- Fetched assets: `8` / `8`
- Passed assets: `0`
- Failed reasons: `['majority_assets_pass_asset_rule', 'all_fetched_assets_drawdown_win_all_windows', 'aggregate_cross_asset_policy_return_positive']`
- Aggregate cross-asset policy return sum: `-3.048518`

## Boundary

- Production impact: Read-only historical transfer replay through the same shared policy functions; production crypto sleeve remains BTC-only.
- Why: The unchanged daily crypto trend policy did not transfer under the predeclared batched rule: majority_assets_pass_asset_rule;all_fetched_assets_drawdown_win_all_windows;aggregate_cross_asset_policy_return_positive
- Forbidden retry: Do not rerun this batch by changing asset list, EMA/SMA spans, target percentages, hysteresis, fee assumptions, window boundaries, annualization, or majority thresholds to flip the verdict. Do not continue consuming altcoins one ID at a time.
- New evidence required: A valid crypto retry needs materially more saved production crypto forward snapshots, a genuinely different crypto data source such as venue/execution cost or liquidity evidence, or a separately predeclared shared policy family.
