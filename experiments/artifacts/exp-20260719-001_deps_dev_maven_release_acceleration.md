# exp-20260719-001: deps.dev Maven release acceleration

## Decision

`rejected`

The new source contract and all measurement gates before Gate 4 passed, but the
fixed top-three weekly release-acceleration candidate pool reduced aggregate
expected-value score from `6.2057` to `3.5203` (`-2.6854`) and capital-neutral
PnL from `$130,992.35` to `$88,201.66` (`-$42,790.69`). No production path was
changed; `trade_enabled=false`.

## Fixed policy

- Exact effective-dated issuer mapping for 29 first-party Maven coordinates.
- Completed Monday-Sunday week only; versions containing `SNAPSHOT` excluded.
- Current issuer release count at least two and strictly above the prior eight
  completed-week median.
- Rank top three by count minus median; enter at next regular-session open and
  exit at the tenth-session close.
- `$4,000` evidence notional, one active position per ticker, six maximum;
  5 bps entry and 5 bps exit slippage plus 35 bps round-trip costs.
- Capital-neutral Gate 4: 24% funded sleeve plus 76% accepted core.

## Source and outcome-blind density

- Frozen events: `1,298`; successful coordinates: `23/29`; mapped tickers: `19`.
- Canonical event SHA-256: `8a3e33dd703f7d3633ae5bd4843b38d26b68c32ee4639f68854ac761cd25d570`.
- Source manifest SHA-256: `8f360865eaddf41a4e9e759c1b2ad9864ad3e5e3600883b1f366538ebf6cd8b8`.

| Window | Eligible issuer-weeks | Tickers | Top-1 share | Density |
|---|---:|---:|---:|:---:|
| old_thin | 59 | 12 | 23.73% | pass |
| mid_weak | 50 | 12 | 24.00% | pass |
| late_strong | 51 | 12 | 19.61% | pass |

The density preflight ran before any warehouse, baseline, price, or outcome
read. The classifier was also repaired before price access: `release` had been
captured by the broad `lease` keyword and routed to `companyfacts_ratio`; the
dedicated source is now `deps_dev_maven_package_releases` with gate
`candidate_pool_top3_10d`.

## Gate 1-4 result

| Window | Settled | Tickers | Sleeve PnL | EV delta | Capital-neutral PnL delta | Cash/SPY/QQQ |
|---|---:|---:|---:|---:|---:|:---:|
| old_thin | 36 | 12 | $653.37 | -0.0165 | -$1,297.93 | pass |
| mid_weak | 33 | 10 | $1,359.07 | -0.4532 | -$12,343.51 | pass |
| late_strong | 36 | 11 | -$5,637.33 | -2.2157 | -$29,149.25 | fail |

- Gate 2 sentinel contract: pass.
- Gate 3: `160` generated, `117` survived, `73.125%` survival.
- Daily/replay policy parity: pass; no orders emitted.
- Gate 4: fail. All three windows lost capital-neutral EV and PnL;
  old_thin worsened drawdown by `0.51pp`; positive-PnL top-five share was
  `98.98%`.

## Reflection and park condition

The signal had modest standalone value in the first two windows but did not
pay for displaced core capital and lost outright in late_strong. Do not retune
the release-count floor, prior-week span, median threshold, top-N, coordinate
subset, hold, costs, or capital weight on this reconstructed archive.

Reopen only after at least 30 newly closed append-only forward Maven-release
decisions under the unchanged policy have positive matched replacement value
versus cash, SPY, and QQQ, or with a genuinely new data source or gate shape.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -B -m pytest quant\test_deps_dev_maven_release_acceleration_paper_sleeve.py quant\test_experiment_fingerprint.py -q
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260719_001_deps_dev_maven_release_acceleration.py --offline
```

The network refresh command is intentionally omitted from routine reproduction:
the evaluated source bundle is already frozen and hash-bound.
