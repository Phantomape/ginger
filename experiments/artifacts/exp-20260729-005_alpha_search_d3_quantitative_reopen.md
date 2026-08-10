# exp-20260729-005 — D3 quantitative Axis-C reopen contract

## Outcome

Accepted measurement repair. D3 can now admit a parked alpha candidate only when a structured proof machine-verifies materially more settled forward rows and binds the waiver to the exact historical family, representative experiment, readiness lane, surface, policy, and fingerprint.

The contract requires both at least 50% relative growth and at least 10 absolute new settled rows. Missing, stale, malformed, tampered, under-threshold, duplicate, or partially matched proofs fail closed. Any additional unbound exact or near-neighbor blocker remains blocking.

## Files

- `quant/alpha_search_contract.py`
- `quant/alpha_search_engine.py`
- `quant/alpha_search_history.py`
- `scripts/alpha_debate.py`
- `quant/test_alpha_reopen_contract.py`
- `data/experiments/exp-20260729-005/before_measurement.json`
- `data/experiments/exp-20260729-005/after_measurement.json`

## Verification

```powershell
.\.venv\Scripts\python.exe -B -m pytest quant\test_alpha_reopen_contract.py quant\test_alpha_search_contract.py quant\test_alpha_search_engine.py quant\test_alpha_search_history.py quant\test_alpha_search_cli.py quant\test_alpha_promotion_v2.py quant\test_alpha_debate.py -q
```

Independent result: `190 passed in 127.12s`. The implementing worker independently obtained `190 passed in 137.94s`; `git diff --check` also passed apart from existing line-ending notices.

No strategy, signal, ranking, sizing, exit, order, paper, live, or `trade_enabled` behavior changed.
