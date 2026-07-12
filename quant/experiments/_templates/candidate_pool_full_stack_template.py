"""TEMPLATE: full-stack candidate-pool experiment (copy me; do not run in place).

Goal
----
Reach a production / paper-sleeve verdict in ONE experiment instead of across
many rounds. Fill the 5 TODOs below and this runner emits a standardized
verdict: ``reject`` / ``accepted_paper_pending_forward`` / ``live_eligible``.

How to use
----------
1. Reserve an id first:
     .\.venv\Scripts\python.exe -B scripts\experiment.py new ^
        --lane alpha_search ^
        --change-type candidate_pool_full_stack ^
        --hypothesis "One sentence: why this candidate pool should make money." ^
        --single-causal-variable "the one decision hypothesis under test" ^
        --file-slug my_candidate_pool ^
        --trial-family my_candidate_pool ^
        --success-probability 0.35 ^
        --main-failure-modes "thin_sample,concentration_failed,not_incremental"
2. Copy this file to ``quant/experiments/exp_YYYYMMDD_NNN_my_candidate_pool.py``.
3. Implement the 5 TODOs (candidate source, shared sleeve adapter, 3-window
   before/after metrics, execution envelope, forward/parity inputs).
4. Run it; commit the verdict JSON + artifact.

Why one experiment is enough
----------------------------
The same experiment that proves the historical edge (Gate 4) also (a) ships the
shared replay+daily sleeve adapter, (b) declares the live execution envelope,
and (c) designs + parity-tests the kill switch. So the ONLY thing between an
accepted paper sleeve and live capital is forward-row maturation -- calendar
time, not another experiment. See ``docs/agent_experiment_protocol.md`` ->
"Full-Stack Candidate-Pool Contract".

No JavaScript was used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)

EXPERIMENT_ID = "exp-YYYYMMDD-NNN"  # TODO: set to the reserved id


# ---------------------------------------------------------------------------
# TODO 1: candidate source (PIT-safe). Return the rows/tickers your sleeve
# admits per signal day. Must be point-in-time (no lookahead).
# ---------------------------------------------------------------------------
def load_candidate_pool() -> Any:
    raise NotImplementedError("TODO 1: load the PIT-safe candidate pool")


# ---------------------------------------------------------------------------
# TODO 2: shared sleeve adapter. Implement ONE helper (a `*_paper_sleeve.py`
# module) that BOTH historical replay and the daily default-off snapshot call,
# so production-visibility and the backtest share code. Do not write a private
# one-off scorer. Model on quant/finra_iwm_paper_sleeve.py or
# quant/fundamental_growth_rs_paper_sleeve.py.
# ---------------------------------------------------------------------------
def build_shared_sleeve_adapter():
    raise NotImplementedError("TODO 2: wire the shared replay+daily sleeve adapter")


# ---------------------------------------------------------------------------
# TODO 3: 3-window canonical before/after metrics. Run the canonical 3-window
# backtest (see docs/backtesting.md) with and without the sleeve and return a
# metrics dict with these keys (deltas are after-minus-before):
#   aggregate_ev_delta, aggregate_pnl_delta,
#   windows_ev_improved, windows_ev_regressed,
#   adjusted_trade_count, adjusted_window_count, max_drawdown_worse_max,
#   single_ticker_positive_share (+ baseline_*), top_5_contribution_pct
#   (+ baseline_*), hhi_concentration (+ baseline_*),
#   avg_pnl_per_trade_delta, avg_return_delta_pp
# ---------------------------------------------------------------------------
def compute_window_metrics() -> dict[str, Any]:
    raise NotImplementedError("TODO 3: run the 3-window backtest, return metrics dict")


# ---------------------------------------------------------------------------
# TODO 4: declare the live execution envelope. Every field must be a real,
# measured/decided value before the sleeve can become live_eligible. Leaving a
# field None is allowed while paper-pending -- it just shows up as a remaining
# checklist item. Fill them all here so live promotion is a config change.
# ---------------------------------------------------------------------------
def declare_execution_envelope() -> ExecutionEnvelope:
    return ExecutionEnvelope(
        base_notional=None,            # TODO: per-position notional
        max_capital_pct=None,          # TODO: sleeve capital cap
        min_dollar_volume=None,        # TODO: liquidity floor for admission
        slippage_bps=None,             # TODO: assumed slippage used in fills
        max_displacement=None,         # TODO: max core/cash candidates displaced
        max_concurrent=None,           # TODO: max concurrent sleeve positions
        order_semantics=None,          # TODO: e.g. "next_open"
        kill_switch_drawdown_pct=None, # TODO: sleeve kill-switch drawdown trigger
        sleeve_drawdown_stop_pct=None, # TODO: sleeve-level drawdown stop
        notes=None,
    )


# ---------------------------------------------------------------------------
# TODO 5: forward + parity inputs for Gate 5. On a FIRST run these are usually
# immature (0 closed forward trades, kill-switch parity may still be passing if
# you wrote the parity test in this experiment). That is expected -- the verdict
# will land at accepted_paper_pending_forward. ``dsr_report`` must come from
# scripts/deflated_sharpe.py over the complete aligned selection panel; do not
# fill it from a rounded Sharpe or prior_trial_count.
# ---------------------------------------------------------------------------
def collect_live_readiness_inputs() -> dict[str, Any]:
    return {
        "closed_forward_trades": 0,        # TODO: closed forward 10d paper trades
        "forward_pnl": None,               # TODO: forward paper PnL once it exists
        "replacement_value_passed": False, # TODO: replacement value vs core/cash
        "kill_switch_parity_passed": False,# TODO: True once parity test added+green
        "dsr_report": None,                 # TODO: full deflated_sharpe.py report (recomputed)
    }


def run() -> dict[str, Any]:
    load_candidate_pool()
    build_shared_sleeve_adapter()

    window_metrics = compute_window_metrics()
    envelope = declare_execution_envelope()
    fwd = collect_live_readiness_inputs()

    gate4 = evaluate_gate4(window_metrics)
    live_readiness = evaluate_live_readiness(envelope=envelope, **fwd)
    verdict = full_stack_verdict(
        gate4=gate4, live_readiness=live_readiness, envelope=envelope
    )

    out_dir = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "full_stack_verdict.json"
    out_path.write_text(
        json.dumps(verdict, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return verdict


def main() -> None:
    verdict = run()
    print(json.dumps(
        {k: verdict[k] for k in ("verdict", "gate4_passed", "live_ready", "next_step")},
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
