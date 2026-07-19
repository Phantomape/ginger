# exp-20260718-006 — Hacker News owned-domain attention

## Decision

`rejected`

The fixed candidate-pool policy passed the source, field, density, and survival checks but failed Gate 4. The capital-neutral 24% sleeve plus 76% core portfolio reduced aggregate expected-value score by `2.1771` and PnL by `$39,611.22`; no canonical window improved.

## Profitable hypothesis and locked policy

A completed UTC week's acceleration in Hacker News links to an issuer's predeclared owned domains could lead developer adoption and product demand. The policy was frozen before price access:

- exact owned-host mapping and object-ID deduplication;
- completed UTC weeks only;
- current count at least two and above the prior four-week mean;
- top three positive accelerations per week;
- next regular-session open, ten-session hold;
- `$4,000` paper notional, one active position per ticker, maximum six positions;
- 5 bps entry plus 5 bps exit slippage and 35 bps round-trip cost;
- capital-neutral measurement at 24% HN sleeve plus 76% core;
- `trade_enabled=false`.

## Source and preflight

The recursively fetched Algolia archive contains `67,647` exact-host stories across `38` mapped tickers. The canonical story-set SHA-256 is `edfc023e41fdb206cab656287657d455abb91287a8044dbaa823fbd7f5353da6`.

Outcome-blind mapped issuer-weeks were `426 / 379 / 382` across `37 / 34 / 36` tickers in `old_thin / mid_weak / late_strong`; top-one shares were about `6.6%`. The locked acceleration rule left `143 / 151 / 149` eligible issuer-weeks, clearing the required density contract.

The Algolia endpoint is a mutable search index and can reflect deletions or index rebuilds. The raw rows, request audit, hashes, and this survivorship caveat are frozen in `data/non_ohlcv/hacker_news_attention/source_manifest.json`; append-only forward rows would be stronger evidence.

## Gate results

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| Aggregate expected-value score | 6.2057 | 4.0286 | -2.1771 |
| Aggregate PnL | $130,992.35 | $91,381.13 | -$39,611.22 |
| Total return | 43.6641% | 30.4604% | -13.2037 pp |
| Max drawdown | 8.89% | 11.84% | +2.95 pp |

Gate 2 passed: the historical source was frozen and `entry_date` and ATR-derived `target_price` were present. Gate 3 passed: `460` signals were generated, `170` survived (`36.9565%`), and `158` settled sleeve trades covered `24` tickers.

| Window | Eligible | Settled trades | Tickers | Sleeve PnL | Combined EV delta | Combined PnL delta | Replacement check |
|---|---:|---:|---:|---:|---:|---:|---|
| old_thin | 151 | 59 | 20 | -$3,094.17 | -0.0879 | -$5,306.46 | failed cash/SPY/QQQ |
| mid_weak | 155 | 52 | 21 | $2,333.97 | -0.3994 | -$11,066.25 | passed |
| late_strong | 154 | 47 | 15 | -$2,140.47 | -1.6898 | -$23,238.51 | failed cash/SPY/QQQ |

Positive-PnL top-five concentration was `73.7239%`, above the 60% guard. The policy failed the aggregate EV and PnL hurdles, all-window non-regression, drawdown, benchmark replacement, concentration, and accepted-comparator checks.

## Reflection and park condition

Density was not the blocker. The attention acceleration did not pay for opportunity cost: only `mid_weak` produced positive standalone sleeve PnL, while every capital-neutral combined window lost money.

Do not retry by changing the story-count floor, prior-week lookback, acceleration threshold, top-k, holding period, notional, issuer subset, or response function on this reconstructed archive. Reopen only with an immutable as-published HN source that materially changes historical membership, or at least 30 newly settled append-only forward issuer-week rows across at least 10 tickers under a predeclared new gate shape.

## Production and reproduction

No production behavior changed. The shared helper and frozen source remain solely for reproduction; no `run.py`, live ranking, sizing, exits, order semantics, or configuration was retained.

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260718_006_hacker_news_owned_domain_attention.py --offline
.\.venv\Scripts\python.exe -B -m pytest quant\test_hacker_news_attention_paper_sleeve.py quant\test_experiment_fingerprint.py -q
```

Canonical result files: `data/experiments/exp-20260718-006/result.json`, `before.json`, `after.json`, `full_stack_verdict.json`, and `daily_default_off_snapshot.json`.
