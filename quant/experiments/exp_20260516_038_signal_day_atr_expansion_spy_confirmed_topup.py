"""exp-20260516-038: SPY-confirmed signal-day ATR expansion top-up.

The broad ATR-expansion top-up in exp-20260516-026/027 had positive aggregate
PnL but failed the three-window gate because the state was still too broad.
This scout tests one narrower, production-visible discriminator: the signal day
must show both top-quartile ATR expansion and ticker open-to-close
outperformance versus SPY.

Replay scout only. No production-default behavior changes unless a separate
shared-policy promotion is made and revalidated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

import exp_20260516_026_signal_day_atr_expansion_topup as broad


EXPERIMENT_ID = "exp-20260516-038"
EXPERIMENT_SLUG = "signal_day_atr_expansion_spy_confirmed_topup"
MULTIPLIER_KEY = "signal_day_atr_expansion_spy_confirmed_topup_multiplier_applied"
STATE_KEY = "signal_day_atr_expansion_spy_confirmed_state"
EXCLUDED_SECTORS = {
    "ETF",
    "Commodities",
}


def _make_confirmed_enrich_wrapper(
    original: Callable[..., list[dict[str, Any]]],
) -> Callable[..., list[dict[str, Any]]]:
    def wrapped(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original(signals, features_dict, atr_target_mult=atr_target_mult)
        cutoff = broad.scout._atr_expansion_top_quartile_cutoff(features_dict)
        cutoff_for_log = (
            round(cutoff, 6) if isinstance(cutoff, (int, float)) else None
        )
        for sig in enriched:
            features = features_dict.get(str(sig.get("ticker") or "")) or {}
            atr_expansion = features.get("atr_expansion")
            sector = sig.get("sector")
            sig["signal_day_atr_expansion"] = atr_expansion
            sig["signal_day_atr_expansion_top_quartile_cutoff"] = cutoff_for_log
            sig[STATE_KEY] = (
                sig.get("strategy") in broad.scout.STATE_STRATEGIES
                and sector not in EXCLUDED_SECTORS
                and isinstance(atr_expansion, (int, float))
                and isinstance(cutoff, (int, float))
                and float(atr_expansion) >= cutoff
                and sig.get("signal_day_ticker_green_candle") is True
                and sig.get("signal_day_ticker_outperformed_spy") is True
            )
        return enriched

    return wrapped


def _markdown(payload: dict[str, Any]) -> str:
    sweep_rows = [
        "| Multiplier | Control | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Affected | Windows | Max DD worse |",
        "|---:|:---:|:---:|---:|---:|---|---|---:|---|---:|",
    ]
    for row in payload["sweep_summary"]:
        sweep_rows.append(
            "| {mult:.4f} | {control} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {affected} | {windows} | {dd:+.4f} |".format(
                mult=row["risk_multiplier"],
                control="yes" if row["is_identity_control"] else "no",
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                affected=row["affected_signal_count"],
                windows=", ".join(row["affected_windows"]) or "-",
                dd=row["max_drawdown_worse"],
            )
        )

    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Max DD d | Survival | Affected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in broad.scout.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {ddd:+.4f} | {surv:.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                ddd=delta.get("max_drawdown_pct", 0.0),
                surv=after["survival_rate"],
                affected=len(payload["adjustments"][label]),
            )
        )

    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SPY-Confirmed Signal-Day ATR Expansion Top-Up",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: cap-aware post-sizing top-up for already-qualified trend/breakout stock signals whose signal-day `atr_expansion` is in the same-day non-ETF/non-commodity top quartile and whose signal-day open-to-close return beats SPY. Entries, filters, ranking, exits, targets, universe, LLM/news, heat, slots, and all other sizing states were unchanged.",
            "",
            "## Sweep",
            "",
            *sweep_rows,
            "",
            f"Selected non-control multiplier: `{payload['parameters']['selected_risk_multiplier']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: replay-only scout. A positive promotion must add shared `risk_engine` state and shared `portfolio_engine` sizing attribution, then rerun the canonical three-window backtest before live/default behavior changes.",
        ]
    )


def _configure_broad_module() -> None:
    broad.EXPERIMENT_ID = EXPERIMENT_ID
    broad.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    broad.MULTIPLIER_KEY = MULTIPLIER_KEY
    broad.scout.EXPERIMENT_ID = EXPERIMENT_ID
    broad.scout.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    broad.scout.MULTIPLIER_KEY = MULTIPLIER_KEY
    broad.scout.STATE_KEY = STATE_KEY
    broad.scout.EXCLUDED_SECTORS = EXCLUDED_SECTORS
    broad.scout._make_enrich_wrapper = _make_confirmed_enrich_wrapper
    broad.scout._markdown = _markdown
    broad._markdown = _markdown


def run() -> dict[str, Any]:
    _configure_broad_module()
    payload = broad.run()
    passed = payload["gate4"]["passed"]
    selected = payload["parameters"]["selected_risk_multiplier"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": (
                "accepted_for_shared_policy_implementation"
                if passed
                else "rejected_signal_day_atr_expansion_spy_confirmed_topup"
            ),
            "decision": (
                "accepted_for_shared_policy_implementation"
                if passed
                else "rejected_signal_day_atr_expansion_spy_confirmed_topup"
            ),
            "hypothesis": (
                "Signal-day top-quartile ATR expansion is too broad by itself, "
                "but when the ticker also beats SPY open-to-close on the same "
                "signal day it may identify demand-confirmed breakout strength. "
                "A small cap-aware top-up can improve EV on the fixed core "
                "candidate set without changing entries, filters, ranking, "
                "exits, LLM/news, or candidate pool."
            ),
            "changed_variable": (
                "signal_day_atr_expansion_spy_confirmed_topup_multiplier"
            ),
            "single_causal_variable": (
                "cap-aware post-sizing top-up multiplier for signal-day "
                "top-quartile ATR expansion trend/breakout signals that beat SPY "
                "open-to-close on the signal day"
            ),
            "interpretation": (
                "SPY-confirmed signal-day ATR expansion top-up cleared the canonical three-window scout and requires shared risk/portfolio promotion plus rerun before production use."
                if passed
                else "SPY-confirmed signal-day ATR expansion top-up did not clear the canonical three-window gate."
            ),
            "rejection_reason": None
            if passed
            else "SPY-confirmed signal-day ATR expansion top-up did not clear the canonical three-window gate.",
            "next_evidence_needed": None
            if passed
            else "Do not retry nearby ATR-expansion plus signal-day confirmation top-ups without forward hold-quality evidence or a materially different production-visible discriminator.",
            "related_files": [
                "quant/experiments/exp_20260516_038_signal_day_atr_expansion_spy_confirmed_topup.py",
                f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
                f"docs/experiments/logs/{EXPERIMENT_ID}.json",
                f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
                f"docs/experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
                "docs/experiment_log.jsonl",
            ],
        }
    )
    payload["parameters"]["state_definition"] = {
        "feature": "atr_expansion",
        "cutoff": "same-day non-ETF/non-commodity top quartile",
        "top_fraction": broad.scout.TOP_FRACTION,
        "strategies": sorted(broad.scout.STATE_STRATEGIES),
        "excluded_sectors": sorted(EXCLUDED_SECTORS),
        "required_signal_day_confirmation": [
            "signal_day_ticker_green_candle is true",
            "signal_day_ticker_outperformed_spy is true",
        ],
    }
    payload["parameters"]["selected_risk_multiplier"] = selected
    payload["gate_questions"]["1_alpha_hypothesis"] = (
        "risk allocation on a production-visible ATR-expansion plus same-day "
        "ticker-vs-SPY confirmation state; this follows the playbook preference "
        "for fixed candidate-set allocation and uses the broad ATR failure to "
        "narrow the state rather than expanding the candidate pool"
    )
    payload["gate_questions"]["2_history_check"] = {
        "exp-20260516-022": (
            "ATR-expansion as a haircut failed all three windows, so the broad "
            "state is not exhaustion by default."
        ),
        "exp-20260516-026": (
            "Broad ATR-expansion top-up improved late_strong and mid_weak but "
            "regressed old_thin; it needs a demand-confirmation discriminator."
        ),
        "exp-20260516-027": (
            "Sector-only narrowing still regressed late_strong. This run narrows "
            "by signal-day ticker-vs-SPY confirmation instead of by sector."
        ),
        "accepted_signal_day_states": (
            "Own-green and ticker-vs-SPY confirmation already work as small "
            "allocation states; this does not retune them, it tests their "
            "interaction with ATR expansion."
        ),
        "llm_and_candidate_pool": (
            "LLM soft-ranking/SEC fields remain attribution-limited, and recent "
            "candidate-pool additions added noise or old-window regression."
        ),
    }
    payload["gate_questions"]["3_single_causal_variable"] = (
        "signal_day_atr_expansion_spy_confirmed_topup_multiplier with fixed "
        "top-quartile ATR expansion and same-day SPY outperformance state"
    )
    payload["gate_questions"]["5_reproducibility"] = (
        ".venv\\Scripts\\python.exe "
        "quant\\experiments\\exp_20260516_038_signal_day_atr_expansion_spy_confirmed_topup.py"
    )
    payload["production_impact"]["promotion_requirement"] = (
        "If accepted, add the ATR-expansion plus signal-day SPY-confirmation "
        "state and sizing key in shared risk_engine.py/portfolio_engine.py paths "
        "used by both backtester.py and run.py, then rerun all three canonical "
        "windows."
    )
    payload["why_not_other_changes"] = (
        "This avoids LLM/SEC branches because semantic attribution is still "
        "sparse, avoids Space peer/source retries after recent zero-incremental "
        "or drawdown-limited results, avoids FINRA days-to-cover after the "
        "sample-thin exp-20260516-037 rejection, and avoids candidate-pool "
        "expansion because recent breadth additions added old-window noise."
    )
    payload["known_risks"] = [
        "This interaction overlaps accepted signal-day confirmation states; it is valid only if the ATR-expansion interaction adds incremental multi-window EV.",
        "The top-quartile boundary is production-visible but still frozen-window selected.",
        "A positive replay scout is not production-tradable until shared risk and sizing code are promoted and rerun.",
    ]
    payload["anti_js"] = "No JavaScript was used."
    return payload


def main() -> dict[str, Any]:
    result = run()
    broad.scout.base.persist(result)
    return result


if __name__ == "__main__":
    result = main()
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
                "affected_signal_count": result["gate4"]["affected_signal_count"],
                "affected_windows": result["gate4"]["affected_windows"],
                "selected_risk_multiplier": result["parameters"][
                    "selected_risk_multiplier"
                ],
                "anti_js": result["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
