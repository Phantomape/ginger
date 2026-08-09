# exp-20260716-009 cash-feasible low-deployment ETF reopen

This is the explicitly permitted post-measurement-repair rerun of
exp-20260715-005. Both sides use the accepted exp-20260715-010 cash-feasible
Gate-1 anchor. The ETF selector, $10,000 cap, one-position limit, next-open
entry, 10-session close, costs, and greater-than-10-percent EV hurdle are
unchanged.

The dated composition contract books core exits first. If a later core entry
needs cash, the ETF is sold at that day's open before the core entry. No core
shares may be displaced, and the ETF may not create negative cash.

Reproduce with:

`.\.venv\Scripts\python.exe -B quant\experiments\exp_20260716_low_deployment_etf_cash_feasible_reopen.py`
