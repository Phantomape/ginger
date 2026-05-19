# exp-20260516-039 TSM Core Adaptation

Decision: `accepted_for_shared_policy_implementation`.

## 038A lifecycle diagnostic

- TSM trade count: `4`
- TSM total PnL: `$-599.72`
- Fast-target supported: `False`
- Branch recommendation: `prioritize_core_quarantine`

## 038B risk scalar sweep

| Multiplier | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Trades | Max DD worse |
|---:|:---:|---:|---:|---|---|---:|---:|---:|---:|
| 1.00 | CTRL | +0.0000 | $+0.00 | - | - | 0 | 0 | 62 | +0.0000 |
| 0.75 | PASS | +0.0039 | $+181.56 | late_strong, mid_weak, old_thin | - | 4 | 3 | 61 | +0.0000 |
| 0.50 | PASS | +0.0117 | $+451.97 | late_strong, mid_weak, old_thin | - | 4 | 3 | 61 | +0.0001 |
| 0.25 | PASS | +0.0143 | $+607.71 | late_strong, mid_weak, old_thin | - | 4 | 3 | 61 | +0.0001 |
| 0.00 | FAIL | -0.0757 | $-3,039.34 | late_strong, mid_weak | old_thin | 4 | 3 | 59 | +0.0000 |

Selected non-control multiplier: `0.25`.

## Selected three-window result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Survival | Affected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1344 | 5.1361 | +0.0017 | $116,686.40 | $116,727.26 | $+40.86 | +0.0000 | 0.8039 | 1 |
| mid_weak | 2.1054 | 2.1065 | +0.0011 | $76,563.68 | $76,595.08 | $+31.40 | +0.0000 | 0.7925 | 1 |
| old_thin | 0.5295 | 0.5410 | +0.0115 | $37,292.45 | $37,827.90 | $+535.45 | +0.0001 | 0.8667 | 2 |

Production impact: promoted into shared `constants.py` / `portfolio_engine.py` as `TSM_CORE_RISK_MULTIPLIER = 0.25`; canonical three-window replay was rerun after promotion and matched the selected scout metrics.
