# exp-20260627-006 Trend Long Entry Latency Attribution

## Decision

- Status: observed_only
- Decision: observed_entry_latency_lead
- Observed gate passed: True
- Failed reasons: none

## Main Read

- Actual trend_long trades analyzed: 39
- Trades with a latest 1-5 session precursor: 24 (0.6154)
- Median lead vs actual entry: 1.0 sessions
- Median entry price advantage: 0.019161
- Median 10d delta: 0.024586
- Median 20d delta: 0.006724
- Median return-to-actual-exit delta: 0.020845
- Median pre-entry MAE before actual entry: -0.009378

## Interpretation

The edge appeared because the diagnostic conditioned on actual trend_long trades instead of replaying a broad prebreakout candidate pool. Most useful rows were already above the prior 20-day high but had volume between 1.0x and 2.0x, so the official 2x volume confirmation often delayed entry by one session without much added pre-entry drawdown. The late_strong window stayed mixed, which is why this is a lead rather than an entry rule.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -B quant\experiments\exp_20260627_006_trend_long_entry_latency_attribution.py
```
