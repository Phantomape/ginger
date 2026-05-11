"""exp-20260511-015: Space official-catalyst breakout risk-distance gate.

The accepted default-off Space hypothesis from exp-20260511-011 keeps the
official-catalyst pool at 0.75x risk. Trend-only filtering was too blunt in
exp-20260511-012. This experiment changes one narrower variable: require
Space official-catalyst breakout_long entries to have a bounded ex-ante
entry-to-stop risk distance, while leaving trend entries, pool membership,
0.75x risk, core A/B behavior, ranking, slots, exits, and LLM/news unchanged.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
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


EXPERIMENT_ID = "exp-20260511-015"
STEM = "space_breakout_risk_distance_gate"
RISK_SCALAR = 0.75
BREAKOUT_RISK_DISTANCE_MAX_VARIANTS = (0.08, 0.09, 0.10, 0.12)
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02

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


def _initial_risk_pct(signal: dict[str, Any]) -> float | None:
    try:
        entry = float(signal.get("entry_price") or 0.0)
        stop = float(signal.get("stop_price") or 0.0)
    except (TypeError, ValueError):
        return None
    if entry <= 0 or stop <= 0 or stop >= entry:
        return None
    return (entry - stop) / entry


@contextmanager
def _patched_space_breakout_risk_distance_gate(max_initial_risk_pct: float):
    import signal_engine  # noqa: PLC0415

    original = signal_engine.generate_signals
    official = {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS}
    removed: list[dict[str, Any]] = []

    def wrapped(features_dict, *args, **kwargs):
        signals = original(features_dict, *args, **kwargs)
        kept = []
        for sig in signals:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            risk_distance = _initial_risk_pct(sig)
            if (
                ticker in official
                and strategy == "breakout_long"
                and risk_distance is not None
                and risk_distance > max_initial_risk_pct
            ):
                removed.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "entry_price": _round(sig.get("entry_price"), 4),
                        "stop_price": _round(sig.get("stop_price"), 4),
                        "initial_risk_pct": _round(risk_distance, 6),
                        "confidence_score": _round(sig.get("confidence_score"), 4),
                        "trade_quality_score": _round(sig.get("trade_quality_score"), 4),
                    }
                )
                continue
            kept.append(sig)
        return kept

    signal_engine.generate_signals = wrapped
    try:
        yield removed
    finally:
        signal_engine.generate_signals = original


def _filter_summary(removed: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker = Counter(row["ticker"] for row in removed)
    by_risk_bucket = Counter()
    for row in removed:
        risk = row.get("initial_risk_pct")
        if risk is None:
            by_risk_bucket["unknown"] += 1
        elif risk <= 0.09:
            by_risk_bucket["lte_9pct"] += 1
        elif risk <= 0.10:
            by_risk_bucket["gt_9_lte_10pct"] += 1
        elif risk <= 0.12:
            by_risk_bucket["gt_10_lte_12pct"] += 1
        else:
            by_risk_bucket["gt_12pct"] += 1
    return {
        "removed_signal_count": len(removed),
        "removed_by_ticker": dict(sorted(by_ticker.items())),
        "removed_by_initial_risk_bucket": dict(sorted(by_risk_bucket.items())),
        "sample_removed": removed[:12],
    }


def _refinement_gate(
    core_agg: dict[str, Any],
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_vs_before: dict[str, dict[str, Any]],
    delta_vs_core: dict[str, dict[str, Any]],
    after_space_attr: dict[str, Any],
) -> dict[str, Any]:
    agg_delta_vs_before = _delta(after_agg, before_agg)
    agg_delta_vs_core = _delta(after_agg, core_agg)
    ev_improved_vs_before = sum(
        1 for delta in delta_vs_before.values() if delta.get("expected_value_score", 0.0) > 0
    )
    ev_regressed_vs_before = sum(
        1 for delta in delta_vs_before.values() if delta.get("expected_value_score", 0.0) < 0
    )
    ev_improved_vs_core = sum(
        1 for delta in delta_vs_core.values() if delta.get("expected_value_score", 0.0) > 0
    )
    max_dd_worsening_vs_core = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_vs_core.values()
    )
    max_dd_change_vs_before = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_vs_before.values()
    )
    passed = (
        agg_delta_vs_before.get("expected_value_score_sum", 0.0) > 0
        and agg_delta_vs_before.get("total_pnl_sum", 0.0) >= 0
        and ev_improved_vs_before >= 2
        and ev_regressed_vs_before <= 1
        and ev_improved_vs_core == len(WINDOWS)
        and max_dd_worsening_vs_core <= MAX_DRAWDOWN_DAMAGE_VS_CORE
        and max_dd_change_vs_before <= 0
        and after_agg.get("min_survival_rate", 0.0) >= 0.05
        and (
            after_space_attr["single_ticker_positive_share"] is None
            or after_space_attr["single_ticker_positive_share"] <= 0.70
        )
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": agg_delta_vs_before,
        "aggregate_delta_vs_core": agg_delta_vs_core,
        "windows_ev_improved_vs_before": ev_improved_vs_before,
        "windows_ev_regressed_vs_before": ev_regressed_vs_before,
        "windows_ev_improved_vs_core": ev_improved_vs_core,
        "max_drawdown_worsening_vs_core": _round(max_dd_worsening_vs_core, 4),
        "max_drawdown_change_vs_before": _round(max_dd_change_vs_before, 4),
    }


def _run_variant(
    max_initial_risk_pct: float,
    core_universe: list[str],
) -> dict[str, Any]:
    by_window: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        included = sorted(set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers)
        candidate_universe = sorted(set(core_universe) | set(included))

        core = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )
        before = _run_window(
            label,
            spec,
            candidate_universe,
            spec["candidate_snapshot"],
            scalar=RISK_SCALAR,
        )
        with _patched_space_breakout_risk_distance_gate(max_initial_risk_pct) as removed:
            after = _run_window(
                label,
                spec,
                candidate_universe,
                spec["candidate_snapshot"],
                scalar=RISK_SCALAR,
            )

        by_window[label] = {
            "window": spec,
            "included_space_tickers": included,
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
            "space_breakout_risk_distance_filter": _filter_summary(removed),
        }

    core_metrics = {label: row["core_metrics"] for label, row in by_window.items()}
    before_metrics = {label: row["before_metrics"] for label, row in by_window.items()}
    after_metrics = {label: row["after_metrics"] for label, row in by_window.items()}
    delta_vs_before = {
        label: row["delta_vs_before"] for label, row in by_window.items()
    }
    delta_vs_core = {label: row["delta_vs_core"] for label, row in by_window.items()}
    core_agg = _aggregate(core_metrics)
    before_agg = _aggregate(before_metrics)
    after_agg = _aggregate(after_metrics)
    after_space_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row["after_space_trade_attribution"]
            }
            for label, row in by_window.items()
        }
    )
    before_space_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row["before_space_trade_attribution"]
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
    return {
        "max_initial_risk_pct": max_initial_risk_pct,
        "core_baseline_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "core_aggregate": core_agg,
        "before_aggregate": before_agg,
        "after_aggregate": after_agg,
        "delta_metrics": {
            "by_window_vs_before": delta_vs_before,
            "by_window_vs_core": delta_vs_core,
            "aggregate_vs_before": gate["aggregate_delta_vs_before"],
            "aggregate_vs_core": gate["aggregate_delta_vs_core"],
        },
        "gate": gate,
        "space_trade_attribution": {
            "before": before_space_attr,
            "after": after_space_attr,
        },
        "by_window": by_window,
    }


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})

    variants: dict[str, dict[str, Any]] = {}
    for max_initial_risk_pct in BREAKOUT_RISK_DISTANCE_MAX_VARIANTS:
        row = _run_variant(max_initial_risk_pct, core_universe)
        variants[str(max_initial_risk_pct)] = row

    passing = [row for row in variants.values() if row["gate"]["passed"]]
    if passing:
        best = max(
            passing,
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                row["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants.values(),
            key=lambda row: (
                row["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
                -row["gate"]["max_drawdown_change_vs_before"],
            ),
        )

    if best["gate"]["passed"]:
        decision = "accepted_default_off_breakout_risk_distance_refinement"
        rejection_reason = None
        interpretation = (
            "The accepted official-catalyst Space sleeve improves when high "
            f"entry-to-stop breakout setups are excluded above "
            f"{best['max_initial_risk_pct']:.0%}. This refines the default-off "
            "forward hypothesis only; live slots remain zero."
        )
    else:
        decision = "rejected_breakout_risk_distance_refinement"
        rejection_reason = (
            "No tested Space breakout risk-distance cap improved the accepted "
            "0.75x official-catalyst hypothesis enough to clear the pre-registered "
            "three-window gate."
        )
        interpretation = (
            "Space breakout losses are visible, but a simple entry-to-stop distance "
            "cap is not a robust enough refinement over the accepted 0.75x official "
            "catalyst hypothesis."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Space official-catalyst breakout losses may be concentrated in setups "
            "whose entry-to-stop distance is too wide for the sleeve; capping that "
            "risk distance can preserve trend entries and cleaner breakouts without "
            "discarding all breakout_long exposure."
        ),
        "change_type": "entry_qualification_shadow_replay",
        "changed_variable": "space_official_breakout_initial_risk_pct_max",
        "single_causal_variable": "space_official_breakout_initial_risk_pct_max",
        "parameters": {
            "candidate_pool_source": "exp-20260511-010",
            "before_hypothesis_source": "exp-20260511-011",
            "candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "risk_scalar": RISK_SCALAR,
            "breakout_initial_risk_pct_max_variants": list(BREAKOUT_RISK_DISTANCE_MAX_VARIANTS),
            "best_breakout_initial_risk_pct_max": best["max_initial_risk_pct"],
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "space risk scalar 0.75",
                "Space trend_long eligibility",
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
            "official-catalyst 0.75x; variants use the same pool/scalar and add "
            "only a Space breakout entry-to-stop risk-distance gate."
        ),
        "core_baseline_metrics": best["core_baseline_metrics"],
        "before_metrics": best["before_metrics"],
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best["gate"]["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "core_aggregate": best["core_aggregate"],
        "before_aggregate": best["before_aggregate"],
        "after_aggregate": best["after_aggregate"],
        "variants": variants,
        "best_variant": best,
        "gate_questions": {
            "alpha_hypothesis": (
                "entry qualification / risk allocation: cap Space breakout "
                "entry-to-stop distance while keeping trend entries untouched"
            ),
            "prior_similar_experiments": [
                "exp-20260511-011 accepted official-catalyst membership at 0.75x default-off risk.",
                "exp-20260511-012 rejected removing all Space breakout_long entries.",
                "No prior Space experiment isolated breakout initial-risk distance.",
            ],
            "single_causal_variable": "Space official-catalyst breakout initial risk pct max",
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp-20260511-011, improve at "
                "least 2/3 EV windows versus that hypothesis, stay positive in all "
                "windows versus core, avoid drawdown worsening versus exp-20260511-011, "
                "keep drawdown damage versus core <= 2 pp, survival >= 5%, and keep "
                "Space positive-contribution concentration within guard."
            ),
            "reproducibility": (
                "This script reruns core, accepted Space 0.75x, and all risk-distance "
                "variants across the three docs/backtesting.md snapshots."
            ),
        },
        "gate_results": {
            "gate1": {
                "core_baseline_metrics": best["core_baseline_metrics"],
                "before_hypothesis_metrics": best["before_metrics"],
            },
            "gate2": open_position_audit,
            "gate3": {
                "new_filter_added": True,
                "scope": "Space official-catalyst breakout_long only; core filters unchanged",
                "minimum_after_survival_rate": best["after_aggregate"].get("min_survival_rate"),
                "passed": best["after_aggregate"].get("min_survival_rate", 0.0) >= 0.05,
            },
            "gate4": best["gate"],
        },
        "space_trade_attribution": best["space_trade_attribution"],
        "by_window": best["by_window"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "Space event-state forward data is still below the closed-decision "
                "gate; this tests an ex-ante deterministic risk-distance feature."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": [
            "Keep exp-20260511-011 official-catalyst 0.75x unchanged unless this refinement passes and is surfaced in production metadata.",
            "Do not retry broad all-breakout removal; use more precise ex-ante risk or catalyst-quality evidence.",
            "Collect forward official-catalyst replacement value by strategy and risk-distance bucket.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
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
        "title": "Space breakout risk-distance gate",
        "status": payload["decision"],
        "lane": "alpha_search",
        "single_causal_variable": payload["single_causal_variable"],
        "result": {
            "decision": payload["decision"],
            "best_breakout_initial_risk_pct_max": payload["best_variant"]["max_initial_risk_pct"],
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

    rows = []
    for variant_key, row in payload["variants"].items():
        gate = row["gate"]
        rows.append(
            "| {variant} | {gate_status} | {ev:+.4f} | {pnl:+.2f} | "
            "{dd_before:+.4f} | {dd_core:+.4f} | {improved}/{total} |".format(
                variant=variant_key,
                gate_status="pass" if gate["passed"] else "fail",
                ev=gate["aggregate_delta_vs_before"].get("expected_value_score_sum", 0.0),
                pnl=gate["aggregate_delta_vs_before"].get("total_pnl_sum", 0.0),
                dd_before=gate["max_drawdown_change_vs_before"],
                dd_core=gate["max_drawdown_worsening_vs_core"],
                improved=gate["windows_ev_improved_vs_before"],
                total=len(WINDOWS),
            )
        )

    detail_rows = []
    for label, row in payload["by_window"].items():
        detail_rows.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {dev:+.4f} | "
            "{core_dev:+.4f} | {before_pnl:.2f} | {after_pnl:.2f} | {dpnl:+.2f} | "
            "{removed} |".format(
                label=label,
                before_ev=row["before_metrics"]["expected_value_score"],
                after_ev=row["after_metrics"]["expected_value_score"],
                dev=row["delta_vs_before"].get("expected_value_score", 0.0),
                core_dev=row["delta_vs_core"].get("expected_value_score", 0.0),
                before_pnl=row["before_metrics"]["total_pnl"],
                after_pnl=row["after_metrics"]["total_pnl"],
                dpnl=row["delta_vs_before"].get("total_pnl", 0.0),
                removed=row["space_breakout_risk_distance_filter"]["removed_signal_count"],
            )
        )

    ARTIFACT_MD.write_text(
        "\n".join(
            [
                f"# {EXPERIMENT_ID} Space Breakout Risk-Distance Gate",
                "",
                f"Decision: `{payload['decision']}`.",
                f"Best cap: `{payload['best_variant']['max_initial_risk_pct']:.0%}`.",
                "",
                "## Sweep",
                "",
                "| Max initial risk | Gate | dEV vs before | dPnL vs before | dDD vs before | dDD vs core | EV improved windows |",
                "|---:|---|---:|---:|---:|---:|---:|",
                *rows,
                "",
                "## Best Three-Window Comparison",
                "",
                "| Window | Before EV | After EV | dEV vs before | dEV vs core | Before PnL | After PnL | dPnL | Removed Space signals |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                *detail_rows,
                "",
                "Gate 4: `{}`.".format(
                    "passed" if payload["gate_results"]["gate4"]["passed"] else "failed"
                ),
                "",
                "Interpretation: " + payload["interpretation"],
                "",
                "Production impact: replay-only alpha search. No orders, core ranking, "
                "sizing, live slots, LLM prompt, or production adapter changed by this script.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    state_note = (
        f"\nLatest Space breakout refinement: `{EXPERIMENT_ID}` tested a "
        "Space official-catalyst `breakout_long` entry-to-stop risk-distance cap "
        "on top of the accepted 0.75x default-off hypothesis. The result was "
        f"`{payload['decision']}`: best cap "
        f"`{payload['best_variant']['max_initial_risk_pct']:.0%}`, aggregate EV delta "
        f"versus exp-20260511-011 "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}`, "
        f"aggregate PnL delta "
        f"`$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}`. "
        "Keep Space live slots at zero; any accepted refinement remains default-off "
        "until forward replacement-value evidence matures.\n"
    )
    _append_once(CURRENT_STATE_MD, f"Latest Space breakout refinement: `{EXPERIMENT_ID}`", state_note)

    playbook_note = (
        f"\n### 2026-05-11 mechanism update: Space breakout risk-distance gate\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: capping Space official-catalyst `breakout_long` entry-to-stop "
        "risk distance changed the accepted 0.75x forward hypothesis by aggregate "
        f"EV `{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}` "
        f"and PnL `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}` "
        f"at the best tested cap `{payload['best_variant']['max_initial_risk_pct']:.0%}`.\n\n"
        "Mechanism insight: Space breakout risk needs a more precise ex-ante "
        "quality discriminator than strategy-family labels. Do not repeat all-"
        "breakout removal; future Space refinement should use forward catalyst "
        "quality or risk-distance bucket evidence.\n"
    )
    _append_once(
        PLAYBOOK_MD,
        f"### 2026-05-11 mechanism update: Space breakout risk-distance gate",
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
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
                "best_breakout_initial_risk_pct_max": payload["best_variant"]["max_initial_risk_pct"],
                "aggregate_delta_vs_before": payload["delta_metrics"]["aggregate_vs_before"],
                "aggregate_delta_vs_core": payload["delta_metrics"]["aggregate_vs_core"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
