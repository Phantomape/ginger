# Backlog — ATR Stop Production/Backtest Parity

> Status: **OPEN / investigated, not implemented.** Owner decision pending.
> Type: `measurement_repair` (touches an executable exit rule → needs Gate 1-4 + parity test before any production change).
> Opened: 2026-06-19. Trigger: SNOW ATR_STOP forced EXIT on 2026-06-17 review.

## 1. Finding

Production's held-position ATR stop diverges from the canonical backtest in **three**
ways, none of which were registered in `known_biases` (`EXIT_POLICY_ADVISORY_RULES`
only lists `PROFIT_LADDER_30/50`, `PROFIT_TARGET`, `TIME_STOP`,
`PENDING_REDUCE_EXIT_OVERRIDE` — **not** `ATR_STOP`).

| # | Divergence | Backtest (canonical / `base`) | Production (current) |
|---|------------|-------------------------------|----------------------|
| 1 | Trigger reference | intraday `low <= stop` ([backtester.py:2898](../quant/backtester.py)) | `close <= stop` ([position_manager.py:401](../quant/position_manager.py)) |
| 2 | ATR freshness | **frozen** at entry (`entry − 1.5×ATR_entry`) | **recomputed daily** with today's ATR (`avg_cost − 1.5×ATR_today`, non-legacy) ([trend_signals.py:236](../quant/trend_signals.py)) |
| 3 | Execution timing | resting stop fills **T intraday** | T-close decision → operator executes **T+1** (`forced_rule` EXIT) |

ATR algorithm itself is shared (`compute_exit_levels`, `ATR_STOP_MULT=1.5`,
`ATR_PERIOD=14`) — no formula bug. The gap is execution semantics.

## 2. Evidence — canonical three windows

Probe added **default-off** flags to `quant/backtester.py` (baseline verified
bit-exact with flags off, EV 7.8941 / PnL $234,850.99):

- `--atr-stop-daily-recompute` (divergence 2)
- `--atr-stop-trigger-on-close` (divergence 1)
- `--atr-stop-exit-next-open` (divergence 3, T+1 market-on-open fill)

Aggregate EV across `late_strong` + `mid_weak` + `old_thin`:

| Variant | trigger | ATR | fill | agg EV | agg PnL |
|---------|---------|-----|------|-------:|--------:|
| `base` (accepted baseline) | low | frozen | T intraday | **7.8941** | $234,851 |
| `close` | close | frozen | T intraday | 7.5864 | $217,967 |
| `recompute` | low | daily | T intraday | 6.1964 | $181,821 |
| `full` | close | daily | T intraday | 7.7240 | $221,286 |
| **`prod_t1` (true current prod)** | close | daily | **T+1 open** | **7.3958** | **$216,388** |

### 2×2 (the key result — divergences are NOT separable)

|              | recompute (prod ATR) | frozen (backtest ATR) |
|--------------|---------------------:|----------------------:|
| **low** (resting broker stop) | 6.1964 | **7.8941 ← best** |
| **close** (EOD)               | 7.7240 | 7.5864 |

- Fixing divergence 2 **alone** (freeze, keep close): 7.7240 → 7.5864 = **−0.14 EV (worse)**.
- Adding the real T+1 lag drops current production to **7.3958** (−6.3% EV /
  −$18.5k vs the baseline all alpha is measured against). Damage concentrates in
  `old_thin` (weak/choppy: −39% PnL).
- **Only moving all three together** (resting frozen stop, T-intraday fill) →
  `base` = 7.8941. Net **+0.50 EV / +$18.5k** vs current production.

## 3. Execution feasibility — moomoo OpenAPI (confirmed 2026-06-19)

`OrderType` includes `STOP`, `STOP_LIMIT`, `TRAILING_STOP(_LIMIT)`;
`TimeInForce` includes `GTC`. US stocks support non-DAY TIF (only HK/A-share/
futures market orders are DAY-only). `place_order` exposes `aux_price` (stop
trigger) + `time_in_force`.

Recipe to realize `base` (no intraday judgment needed):
```
place_order(order_type=OrderType.STOP, aux_price=entry−1.5×ATR_entry,
            time_in_force=TimeInForce.GTC, ...)   # frozen, set once at entry
```
- Use `STOP` (market-on-trigger), **not** `STOP_LIMIT` — STOP_LIMIT can fail to
  fill on a gap-through and trap a falling position; backtest assumes a filled
  (gap-aware) stop.
- **Not** `TRAILING_STOP` — that is divergence 2 (recompute), shown worse.
- Caveats: skill `place_order.py` wrapper only exposes NORMAL/MARKET (STOP/GTC
  needs a direct SDK call or wrapper extension); live orders require manual
  trade-password unlock in OpenD GUI.

## 4. Recommended next step (if owner approves)

`measurement_repair` experiment:
1. reserve ID; before = `prod_t1` artifact, after-target = `base` (7.8941).
2. production patch: persist entry-day ATR at position open; emit a frozen GTC
   `STOP` order instead of the EOD `forced_rule` ATR-EXIT advisory.
3. add a parity test asserting backtest `base` stop == production stop level/timing.
4. re-run canonical three windows; confirm baseline unmoved except the intended axis.

Optional de-risk before code: manually place one GTC STOP on SNOW/COHR to observe
moomoo's real fill behavior.

## 5. Open decisions for owner

- [ ] Switch live exits to GTC resting STOP orders? (the only path that improves EV)
- [ ] If no → accept that production sits at the best **EOD** corner (7.7240→7.3958
      with T+1) and register `ATR_STOP` + T+1 lag as documented `known_biases`
      instead of "fixing" (freezing alone is negative).

## 6. Artifacts / files touched (diagnostic only, default-off — nothing accepted)

- `quant/backtester.py` — three default-off probe flags (baseline bit-exact).
- `scripts/atr_stop_parity_probe.py` + `scripts/atr_stop_parity_out.json` — 4×3 matrix.
- `scripts/atr_stop_t1_probe.py` + `scripts/atr_stop_t1_out.json` — T+1 faithful variant.

Repro (one window):
```powershell
.\.venv\Scripts\python.exe quant\backtester.py --start 2024-10-02 --end 2025-04-22 `
  --ohlcv-warehouse data\experiments\exp-20260519-030\warehouse_main.sqlite `
  --ohlcv-warehouse-snapshot-source data\ohlcv\ohlcv_snapshot_20241002_20250422.json `
  --no-oracle-diagnostics `
  --atr-stop-trigger-on-close --atr-stop-daily-recompute --atr-stop-exit-next-open
```
