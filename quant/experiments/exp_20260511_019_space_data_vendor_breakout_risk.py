"""exp-20260511-019: Space data-vendor breakout risk haircut.

exp-20260511-018 rejected deleting PL/BKSY breakout entries because the slot
path damage outweighed the removed losses. This experiment keeps those signals
eligible but changes one variable: an extra risk scalar for PL/BKSY
breakout_long entries inside the accepted official-catalyst 0.75x Space sleeve.
"""

from __future__ import annotations

import json
import math
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for path in (str(EXPERIMENTS_DIR), str(QUANT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data_layer import get_universe  # noqa: E402
from exp_20260511_002_space_catalyst_static_pool_replay import (  # noqa: E402
    WINDOWS,
    _aggregate,
    _delta,
    _open_position_field_audit,
    _round,
    _snapshot_tickers,
)
from exp_20260511_009_space_static_pool_risk_scalar import (  # noqa: E402
    _run_window,
    _space_trade_attribution,
)
from exp_20260511_010_space_official_catalyst_subpool import (  # noqa: E402
    OFFICIAL_CATALYST_TICKERS,
    _aggregate_space_attr,
    _append_jsonl_once,
    _append_once,
    _write_json,
)
from exp_20260511_018_space_data_vendor_trend_gate import (  # noqa: E402
    DATA_VENDOR_TICKERS,
    _refinement_gate,
)


EXPERIMENT_ID = "exp-20260511-019"
STEM = "space_data_vendor_breakout_risk"
RISK_SCALAR = 0.75
DATA_VENDOR_BREAKOUT_SCALARS = (0.75, 0.5, 0.25)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


def _scale_sizing(sizing: dict[str, Any], scalar: float, portfolio_value: float) -> None:
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return
    new_shares = int(math.floor(old_shares * scalar))
    ratio = new_shares / old_shares if old_shares else 0.0
    old_risk_pct = float(sizing.get("risk_pct") or 0.0)
    old_risk_amount = float(
        sizing.get("risk_amount_usd") or (old_risk_pct * portfolio_value)
    )
    old_position_value = float(sizing.get("position_value_usd") or 0.0)
    sizing["space_data_vendor_breakout_risk_scalar_applied"] = scalar
    sizing["space_data_vendor_breakout_baseline_shares"] = old_shares
    sizing["space_data_vendor_breakout_scaled_shares"] = new_shares
    sizing["space_data_vendor_breakout_risk_pct_before_scalar"] = old_risk_pct
    sizing["space_data_vendor_breakout_risk_amount_before_scalar"] = round(
        old_risk_amount,
        2,
    )
    sizing["shares_to_buy"] = new_shares
    sizing["risk_pct"] = old_risk_pct * ratio
    sizing["risk_amount_usd"] = round(old_risk_amount * ratio, 2)
    sizing["position_value_usd"] = round(old_position_value * ratio, 2)
    sizing["position_pct_of_portfolio"] = (
        round((old_position_value * ratio) / portfolio_value, 4)
        if portfolio_value
        else 0.0
    )


@contextmanager
def _patched_data_vendor_breakout_scalar(scalar: float):
    import portfolio_engine  # noqa: PLC0415

    original = portfolio_engine.size_signals
    data_vendors = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    adjusted: list[dict[str, Any]] = []

    def wrapped(signals, portfolio_value, risk_pct=None):
        sized = original(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            sizing = sig.get("sizing")
            if ticker in data_vendors and strategy == "breakout_long" and sizing:
                before_shares = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(sizing, scalar, portfolio_value)
                adjusted.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "entry_price": _round(sig.get("entry_price"), 4),
                        "scalar": scalar,
                        "shares_before_extra_scalar": before_shares,
                        "shares_after_extra_scalar": int(
                            sizing.get("shares_to_buy") or 0
                        ),
                        "trade_quality_score": _round(
                            sig.get("trade_quality_score"),
                            4,
                        ),
                        "confidence_score": _round(sig.get("confidence_score"), 4),
                    }
                )
        return sized

    portfolio_engine.size_signals = wrapped
    try:
        yield adjusted
    finally:
        portfolio_engine.size_signals = original


def _run_variant(
    label: str,
    spec: dict[str, str],
    core_universe: list[str],
    included: list[str],
    scalar: float,
) -> dict[str, Any]:
    candidate_universe = sorted(set(core_universe) | set(included))
    with _patched_data_vendor_breakout_scalar(scalar) as adjusted:
        result = _run_window(
            label,
            spec,
            candidate_universe,
            spec["candidate_snapshot"],
            scalar=RISK_SCALAR,
        )
    result["data_vendor_breakout_adjustments"] = adjusted
    return result


def _adjustment_summary(adjusted: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "adjusted_signal_count": len(adjusted),
        "adjusted_by_ticker": {
            ticker: sum(1 for row in adjusted if row["ticker"] == ticker)
            for ticker in sorted({row["ticker"] for row in adjusted})
        },
        "sample_adjusted": adjusted[:16],
    }


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})

    core_by_window: dict[str, dict[str, Any]] = {}
    before_by_window: dict[str, dict[str, Any]] = {}
    included_by_window: dict[str, list[str]] = {}

    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        included = sorted(set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers)
        included_by_window[label] = included
        candidate_universe = sorted(set(core_universe) | set(included))
        core_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before_by_window[label] = _run_window(
            label,
            spec,
            candidate_universe,
            spec["candidate_snapshot"],
            scalar=RISK_SCALAR,
        )

    core_metrics = {label: row["metrics"] for label, row in core_by_window.items()}
    before_metrics = {
        label: row["metrics"] for label, row in before_by_window.items()
    }
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)

    variants: dict[str, dict[str, Any]] = {}
    for scalar in DATA_VENDOR_BREAKOUT_SCALARS:
        by_window: dict[str, dict[str, Any]] = {}
        for label, spec in WINDOWS.items():
            included = included_by_window[label]
            after = _run_variant(label, spec, core_universe, included, scalar)
            before = before_by_window[label]
            core = core_by_window[label]
            by_window[label] = {
                "window": spec,
                "included_space_tickers": included,
                "data_vendor_tickers": sorted(
                    set(DATA_VENDOR_TICKERS) & set(included)
                ),
                "core_metrics": core["metrics"],
                "before_metrics": before["metrics"],
                "after_metrics": after["metrics"],
                "delta_vs_core": _delta(after["metrics"], core["metrics"]),
                "delta_vs_before": _delta(after["metrics"], before["metrics"]),
                "before_space_trade_attribution": _space_trade_attribution(
                    before["trades"],
                    set(included),
                ),
                "after_space_trade_attribution": _space_trade_attribution(
                    after["trades"],
                    set(included),
                ),
                "data_vendor_breakout_risk_adjustment": _adjustment_summary(
                    after["data_vendor_breakout_adjustments"]
                ),
            }

        after_metrics = {label: row["after_metrics"] for label, row in by_window.items()}
        delta_vs_before = {
            label: row["delta_vs_before"] for label, row in by_window.items()
        }
        delta_vs_core = {label: row["delta_vs_core"] for label, row in by_window.items()}
        after_agg = _aggregate(after_metrics)
        after_space_attr = _aggregate_space_attr(
            {
                label: {
                    "space_trade_attribution": row["after_space_trade_attribution"]
                }
                for label, row in by_window.items()
            }
        )
        gate = _refinement_gate(
            core_agg,
            before_agg,
            after_agg,
            delta_vs_before,
            delta_vs_core,
            after_space_attr,
        )
        variants[str(scalar)] = {
            "data_vendor_breakout_scalar": scalar,
            "after_metrics": after_metrics,
            "after_aggregate": after_agg,
            "delta_metrics": {
                "by_window_vs_before": delta_vs_before,
                "by_window_vs_core": delta_vs_core,
                "aggregate_vs_before": gate["aggregate_delta_vs_before"],
                "aggregate_vs_core": gate["aggregate_delta_vs_core"],
            },
            "gate": gate,
            "space_trade_attribution": {
                "before": _aggregate_space_attr(
                    {
                        label: {
                            "space_trade_attribution": row[
                                "before_space_trade_attribution"
                            ]
                        }
                        for label, row in by_window.items()
                    }
                ),
                "after": after_space_attr,
            },
            "by_window": by_window,
        }

    passing = [row for row in variants.values() if row["gate"]["passed"]]
    if passing:
        best = max(
            passing,
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants.values(),
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )

    if best["gate"]["passed"]:
        decision = "accepted_default_off_data_vendor_breakout_risk_haircut"
        rejection_reason = None
        interpretation = (
            "The accepted Space official-catalyst sleeve improves when PL/BKSY "
            f"breakout entries keep eligibility but receive an extra "
            f"{best['data_vendor_breakout_scalar']}x risk haircut. This refines "
            "the default-off forward hypothesis only; live Space slots remain zero."
        )
    else:
        decision = "rejected_data_vendor_breakout_risk_haircut"
        rejection_reason = (
            "No tested PL/BKSY breakout risk scalar beat the accepted "
            "exp-20260511-011 0.75x Space official-catalyst hypothesis under the "
            "pre-registered three-window gate."
        )
        interpretation = (
            "Keeping PL/BKSY breakouts but hair-cutting their risk is still not "
            "enough to replace the accepted Space official-catalyst 0.75x "
            "hypothesis."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Within the accepted official-catalyst Space sleeve, PL/BKSY breakout "
            "signals may retain useful routing information but deserve a smaller "
            "risk budget than launch, connectivity, lunar, manufacturing, or "
            "PL/BKSY trend entries."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_data_vendor_breakout_risk_scalar",
        "single_causal_variable": "space_data_vendor_breakout_risk_scalar",
        "parameters": {
            "candidate_pool_source": "exp-20260511-010",
            "before_hypothesis_source": "exp-20260511-011",
            "official_candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "data_vendor_tickers": list(DATA_VENDOR_TICKERS),
            "data_vendor_breakout_scalars": list(DATA_VENDOR_BREAKOUT_SCALARS),
            "best_data_vendor_breakout_scalar": best[
                "data_vendor_breakout_scalar"
            ],
            "base_space_risk_scalar": RISK_SCALAR,
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "base Space risk scalar 0.75",
                "data-vendor trend entries",
                "non-data-vendor Space strategy eligibility",
                "core production universe",
                "core signal generation",
                "core entry filters",
                "ranking",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live pilot slots",
            ],
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}"
            for label, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three-window fixed protocol. Core "
            "baseline uses canonical snapshots; before uses exp-20260511-011 "
            "official-catalyst 0.75x; after keeps the same pool/scalar and applies "
            "only an extra PL/BKSY breakout risk scalar."
        ),
        "core_baseline_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best["gate"]["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "core_aggregate": core_agg,
        "before_aggregate": before_agg,
        "after_aggregate": best["after_aggregate"],
        "gate_questions": {
            "alpha_hypothesis": (
                "risk allocation: PL/BKSY breakout entries retain eligibility but "
                "receive an extra risk haircut inside the accepted Space sleeve."
            ),
            "prior_similar_experiments": [
                "exp-20260511-011 accepted the official-catalyst 0.75x default-off hypothesis.",
                "exp-20260511-012 rejected blanket trend-only Space filtering.",
                "exp-20260511-018 rejected deleting PL/BKSY breakout entries.",
                "No prior experiment swept PL/BKSY breakout-only risk haircuts.",
            ],
            "single_causal_variable": "extra PL/BKSY breakout risk scalar.",
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp-20260511-011, improve "
                "at least 2/3 EV windows versus that hypothesis, stay EV-positive "
                "in all windows versus core, keep drawdown damage versus core <= 2 pp, "
                "survival >= 5%, and keep Space positive-contribution concentration within guard."
            ),
            "reproducibility": (
                "This script reruns core, accepted Space 0.75x, and each PL/BKSY "
                "breakout risk scalar variant across the three docs/backtesting.md snapshots."
            ),
        },
        "gate_results": {
            "gate1": {
                "core_baseline_metrics": core_metrics,
                "before_hypothesis_metrics": before_metrics,
            },
            "gate2": open_position_audit,
            "gate3": {
                "new_filter_added": False,
                "scope": "Space official-catalyst PL/BKSY breakout sizing only; core filters unchanged",
                "minimum_after_survival_rate": best["after_aggregate"].get(
                    "min_survival_rate"
                ),
                "passed": best["after_aggregate"].get("min_survival_rate", 0.0) >= 0.05,
            },
            "gate4": best["gate"],
        },
        "space_trade_attribution": best["space_trade_attribution"],
        "variants": variants,
        "best_variant": best,
        "by_window": best["by_window"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "Space event-state forward data is still below the closed-decision "
                "gate; this tests a deterministic subsegment risk-allocation feature."
            ),
        },
        "production_impact": {
            "shared_policy_changed": decision
            == "accepted_default_off_data_vendor_breakout_risk_haircut",
            "backtester_adapter_changed": False,
            "run_adapter_changed": decision
            == "accepted_default_off_data_vendor_breakout_risk_haircut",
            "replay_only": False,
            "parity_test_added": decision
            == "accepted_default_off_data_vendor_breakout_risk_haircut",
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "default_off_observation_only": True,
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": [
            "If accepted, promote only as shared production-visible default-off forward hypothesis metadata/helper; live slots remain zero.",
            "Do not retry PL/BKSY deletion or blanket Space trend-only filtering on this frozen sample.",
            "Collect forward replacement value separately for data-vendor breakouts, data-vendor trends, and hardware/network buckets.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/space_catalyst_sleeve.py",
            "quant/report_generator.py",
            "quant/test_space_catalyst_sleeve.py",
            "docs/production_backtest_parity.md",
            "docs/experiment_log.jsonl",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
        ],
        "interpretation": interpretation,
    }
    return payload


def _write_artifacts(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Space data-vendor breakout risk",
        "status": payload["decision"],
        "lane": "alpha_search",
        "single_causal_variable": payload["single_causal_variable"],
        "result": {
            "decision": payload["decision"],
            "best_scalar": payload["best_variant"]["data_vendor_breakout_scalar"],
            "aggregate_ev_delta_vs_before": payload["delta_metrics"][
                "aggregate_vs_before"
            ].get("expected_value_score_sum"),
            "aggregate_pnl_delta_vs_before": payload["delta_metrics"][
                "aggregate_vs_before"
            ].get("total_pnl_sum"),
            "gate_passed": payload["gate_results"]["gate4"]["passed"],
        },
        "next_steps": payload["next_evidence_needed"],
        "created_at": payload["timestamp"],
    }
    _write_json(TICKET_JSON, ticket)
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, payload)

    lines = [
        f"# {EXPERIMENT_ID} Space Data-Vendor Breakout Risk",
        "",
        f"Decision: `{payload['decision']}`.",
        f"Best data-vendor breakout scalar: `{payload['best_variant']['data_vendor_breakout_scalar']}`.",
        "",
        "## Sweep",
        "",
        "| Scalar | Gate | dEV vs before | dPnL vs before | dDD vs core | EV improved windows |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for scalar_key, row in payload["variants"].items():
        gate = row["gate"]
        lines.append(
            "| {scalar} | {gate_result} | {dev:+.4f} | {dpnl:+.2f} | {ddd:+.4f} | {evw}/3 |".format(
                scalar=scalar_key,
                gate_result="pass" if gate["passed"] else "fail",
                dev=gate["aggregate_delta_vs_before"].get(
                    "expected_value_score_sum",
                    0.0,
                ),
                dpnl=gate["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
                ddd=gate["max_drawdown_worsening_vs_core"],
                evw=gate["windows_ev_improved_vs_before"],
            )
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Adjusted signals |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["by_window"].items():
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {dev:+.4f} | "
            "{core_dev:+.4f} | {before_pnl:.2f} | {after_pnl:.2f} | {dpnl:+.2f} | "
            "{adjusted} |".format(
                label=label,
                before_ev=row["before_metrics"]["expected_value_score"],
                after_ev=row["after_metrics"]["expected_value_score"],
                dev=row["delta_vs_before"].get("expected_value_score", 0.0),
                core_dev=row["delta_vs_core"].get("expected_value_score", 0.0),
                before_pnl=row["before_metrics"]["total_pnl"],
                after_pnl=row["after_metrics"]["total_pnl"],
                dpnl=row["delta_vs_before"].get("total_pnl", 0.0),
                adjusted=row["data_vendor_breakout_risk_adjustment"][
                    "adjusted_signal_count"
                ],
            )
        )
    lines.extend(
        [
            "",
            "Gate 4: `{}`.".format(
                "passed" if payload["gate_results"]["gate4"]["passed"] else "failed"
            ),
            "",
            "Interpretation: " + payload["interpretation"],
            "",
            "Production impact: replay-only alpha search. If accepted, the "
            "forward hypothesis must be promoted through shared Space sleeve "
            "metadata/helper code before any future trade-enabled adapter.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")

    state_note = (
        f"\nLatest Space data-vendor breakout risk refinement: `{EXPERIMENT_ID}` "
        "swept an extra risk scalar for PL/BKSY `breakout_long` entries inside "
        "the accepted official-catalyst Space 0.75x forward hypothesis. The "
        f"best scalar was `{payload['best_variant']['data_vendor_breakout_scalar']}` "
        f"with decision `{payload['decision']}`: aggregate EV delta versus "
        f"exp-20260511-011 "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}`, "
        f"aggregate PnL delta "
        f"`$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}`.\n"
    )
    _append_once(
        CURRENT_STATE_MD,
        f"Latest Space data-vendor breakout risk refinement: `{EXPERIMENT_ID}`",
        state_note,
    )

    playbook_note = (
        f"\n### 2026-05-11 mechanism update: Space data-vendor breakout risk\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: sweeping an extra PL/BKSY `breakout_long` risk scalar inside "
        "the accepted official-catalyst Space 0.75x sleeve produced best scalar "
        f"`{payload['best_variant']['data_vendor_breakout_scalar']}` with "
        "aggregate EV delta "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}` "
        f"and PnL `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}` "
        "versus exp-20260511-011.\n\n"
        "Mechanism insight: do not solve Space data-vendor fragility by deleting "
        "the signal; exp-20260511-018 showed that path damage can dominate. A "
        "risk haircut is the cleaner test, but it still must clear the same "
        "three-window EV standard before becoming a shared forward hypothesis.\n"
    )
    _append_once(
        PLAYBOOK_MD,
        "### 2026-05-11 mechanism update: Space data-vendor breakout risk",
        playbook_note,
    )


def main() -> None:
    payload = run_experiment()
    _write_artifacts(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "best_scalar": payload["best_variant"]["data_vendor_breakout_scalar"],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
                "aggregate_delta_vs_before": payload["delta_metrics"]["aggregate_vs_before"],
                "aggregate_delta_vs_core": payload["delta_metrics"]["aggregate_vs_core"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
