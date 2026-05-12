"""exp-20260512-107: signal-day positive sector-tape risk allocation.

This reuses the exp-20260512-106 replay harness but flips the state variable:
test a small risk top-up when the production-knowable signal-day sector proxy
open-to-close return is >= +1%.
"""

from __future__ import annotations

import json
import math
from typing import Any, Callable

import exp_20260512_106_signal_day_sector_tape_risk as base


EXPERIMENT_ID = "exp-20260512-107"
EXPERIMENT_SLUG = "signal_day_positive_sector_tape_risk"
POSITIVE_TAPE_THRESHOLD = 0.01
POSITIVE_TAPE_RISK_MULTIPLIER = 1.1
MULTIPLIER_KEY = "signal_day_positive_sector_tape_risk_multiplier_applied"


def _make_enrich_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        for sig in enriched:
            sector = sig.get("sector")
            proxy = base.SECTOR_PROXY.get(str(sector or ""))
            proxy_ret = None
            if proxy:
                proxy_ret = (features_dict.get(proxy) or {}).get("signal_day_open_close_return_pct")
            sig["signal_day_sector_proxy"] = proxy
            sig["signal_day_sector_proxy_open_close_return_pct"] = proxy_ret
            sig["signal_day_adverse_sector_tape"] = (
                isinstance(proxy_ret, (int, float))
                and proxy_ret >= POSITIVE_TAPE_THRESHOLD
            )
        return enriched

    return wrapped


def _scale_sizing(sizing: dict[str, Any], scalar: float, portfolio_value: float) -> dict[str, Any]:
    shares = int(sizing.get("shares_to_buy") or 0)
    if shares <= 0:
        return sizing
    entry = float(sizing.get("entry_price") or 0.0)
    if entry <= 0:
        return sizing
    cap_shares = max(1, int(math.floor(portfolio_value * float(sizing.get("max_position_pct_applied") or 0.40) / entry)))
    new_shares = min(cap_shares, max(shares, int(math.floor(shares * scalar))))
    if new_shares <= shares:
        return sizing
    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    out = dict(sizing)
    out["signal_day_positive_sector_tape_baseline_shares"] = shares
    out["signal_day_positive_sector_tape_new_shares"] = new_shares
    out["shares_to_buy"] = new_shares
    out["position_value_usd"] = round(entry * new_shares, 2)
    out["position_pct_of_portfolio"] = round((entry * new_shares) / portfolio_value, 4) if portfolio_value else 0.0
    out["risk_amount_usd"] = round(net_risk_per_share * new_shares, 2)
    out["risk_pct"] = (net_risk_per_share * new_shares) / portfolio_value if portfolio_value else 0.0
    out[MULTIPLIER_KEY] = scalar
    return out


def _make_size_wrapper(original: Callable[..., list[dict[str, Any]]]) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for sig in sized:
            sizing = sig.get("sizing") or {}
            if sig.get("signal_day_adverse_sector_tape") and sizing.get("shares_to_buy"):
                adjusted_sizing = _scale_sizing(sizing, POSITIVE_TAPE_RISK_MULTIPLIER, portfolio_value)
                if adjusted_sizing is not sizing:
                    base.ADJUSTMENTS.append(
                        {
                            "ticker": sig.get("ticker"),
                            "strategy": sig.get("strategy"),
                            "sector": sig.get("sector"),
                            "sector_proxy": sig.get("signal_day_sector_proxy"),
                            "sector_proxy_open_close_return_pct": sig.get(
                                "signal_day_sector_proxy_open_close_return_pct"
                            ),
                            "baseline_shares": sizing.get("shares_to_buy"),
                            "new_shares": adjusted_sizing.get("shares_to_buy"),
                            "trade_quality_score": sig.get("trade_quality_score"),
                            "regime_exit_bucket": sig.get("regime_exit_bucket"),
                            "regime_exit_score": sig.get("regime_exit_score"),
                        }
                    )
                    sig = {**sig, "sizing": adjusted_sizing}
            out.append(sig)
        return out

    return wrapped


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Adjusted signals |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {adj} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                adj=len(payload["adjustments"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Signal-Day Positive Sector Tape Risk",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: 1.10x cap-aware post-sizing risk top-up when the signal-day sector proxy open-to-close return is >= +1%. No entry filter, ranking, exit, target, universe, LLM, or news behavior changed.",
            "",
            *rows,
            "",
            "Production impact: replay-only scout. Positive promotion would require shared `feature_layer`, `risk_engine`, and `portfolio_engine` code plus attribution key parity before live/default behavior changes.",
        ]
    )


def run() -> dict[str, Any]:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    base.ADVERSE_TAPE_THRESHOLD = POSITIVE_TAPE_THRESHOLD
    base.ADVERSE_TAPE_RISK_MULTIPLIER = POSITIVE_TAPE_RISK_MULTIPLIER
    base.MULTIPLIER_KEY = MULTIPLIER_KEY
    base._make_enrich_wrapper = _make_enrich_wrapper
    base._make_size_wrapper = _make_size_wrapper
    base._markdown = _markdown
    payload = base.run()
    passed = payload["gate4"]["passed"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": (
                "accepted_for_shared_policy_implementation"
                if passed
                else "rejected_signal_day_positive_sector_tape_risk"
            ),
            "decision": (
                "accepted_for_shared_policy_implementation"
                if passed
                else "rejected_signal_day_positive_sector_tape_risk"
            ),
            "hypothesis": (
                "Signals fired on days when their sector proxy is already up >=1% open-to-close may have stronger next-session follow-through; apply a small cap-aware risk top-up rather than changing ranking or entries."
            ),
            "changed_variable": "signal_day_positive_sector_tape_risk_multiplier",
            "single_causal_variable": (
                "1.10x cap-aware post-sizing risk top-up for signals whose signal-day sector proxy open-to-close return is >= +1%"
            ),
            "parameters": {
                "positive_tape_threshold": POSITIVE_TAPE_THRESHOLD,
                "risk_multiplier": POSITIVE_TAPE_RISK_MULTIPLIER,
                "sector_proxy": base.SECTOR_PROXY,
                "locked_variables": payload["parameters"]["locked_variables"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": "core state risk allocation using production-knowable signal-day positive sector tape",
                "2_history_check": {
                    "exp-20260512-106": "rejected adverse sector-tape haircut; this tests the opposite continuation state, not another de-risking filter.",
                    "broad_filters": "historically weak; this run does not filter entries or reduce survival.",
                },
                "3_single_causal_variable": "signal_day_positive_sector_tape_risk_multiplier at a fixed +1% state boundary",
                "4_acceptance_standard": "docs/backtesting.md three fixed windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%.",
                "5_reproducibility": "Run .venv\\Scripts\\python.exe quant\\experiments\\exp_20260512_107_signal_day_positive_sector_tape_risk.py",
            },
            "interpretation": (
                "Signal-day positive sector tape improved the accepted core stack and should be implemented through shared feature/risk/sizing policy before any production-visible use."
                if passed
                else "The 1.10x signal-day positive sector-tape risk top-up did not clear the canonical three-window gate; do not promote this fixed threshold/scalar without a stronger discriminator."
            ),
            "rejection_reason": None
            if passed
            else "The 1.10x signal-day positive sector-tape risk top-up did not clear the canonical three-window gate; do not promote this fixed threshold/scalar without a stronger discriminator.",
            "next_evidence_needed": None
            if passed
            else "Use forward/shadow sector-tape continuation attribution or a different production-visible state variable before retrying.",
            "related_files": [
                "quant/experiments/exp_20260512_107_signal_day_positive_sector_tape_risk.py",
                "data/experiments/exp-20260512-107/signal_day_positive_sector_tape_risk.json",
                "docs/experiments/logs/exp-20260512-107.json",
                "docs/experiments/tickets/exp-20260512-107.json",
                "docs/experiments/artifacts/exp-20260512-107_signal_day_positive_sector_tape_risk.md",
                "docs/experiment_log.jsonl",
            ],
        }
    )
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
    }
    return payload


if __name__ == "__main__":
    result = run()
    base.persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "gate4_passed": result["gate4"]["passed"],
                "improved_windows": result["gate4"]["improved_windows"],
                "regressed_windows": result["gate4"]["regressed_windows"],
                "adjusted_signal_count": result["gate4"]["adjusted_signal_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
