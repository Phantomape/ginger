"""exp-20260511-016: Space official-catalyst RS20 leader gate.

The current accepted Space forward hypothesis is the locked official-catalyst
subpool at 0.75x risk from exp-20260511-011. This experiment changes one
ex-ante quality variable inside that hypothesis: require Space official
catalyst entries to already carry the existing rs20_entry_state_leader flag
from shared risk enrichment. It does not retune the RS20 threshold, risk
scalar, pool, entry logic, ranking, exits, add-ons, LLM/news, or live slots.
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


EXPERIMENT_ID = "exp-20260511-016"
STEM = "space_official_rs20_leader"
RISK_SCALAR = 0.75
MAX_DRAWDOWN_DAMAGE_VS_CORE = 0.02

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


@contextmanager
def _patched_space_rs20_leader_gate():
    import risk_engine  # noqa: PLC0415

    original = risk_engine.enrich_signals
    official = {ticker.upper() for ticker in OFFICIAL_CATALYST_TICKERS}
    removed: list[dict[str, Any]] = []

    def wrapped(signals, *args, **kwargs):
        enriched = original(signals, *args, **kwargs)
        kept = []
        for sig in enriched:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker in official and sig.get("rs20_entry_state_leader") is not True:
                removed.append(
                    {
                        "ticker": ticker,
                        "strategy": str(sig.get("strategy") or "unknown"),
                        "entry_price": _round(sig.get("entry_price"), 4),
                        "confidence_score": _round(sig.get("confidence_score"), 4),
                        "trade_quality_score": _round(sig.get("trade_quality_score"), 4),
                        "ticker_ret20_minus_spy_pct": _round(
                            sig.get("ticker_ret20_minus_spy_pct"),
                            4,
                        ),
                        "spy_relative_leader": sig.get("spy_relative_leader"),
                        "rs20_entry_state_leader": sig.get("rs20_entry_state_leader"),
                    }
                )
                continue
            kept.append(sig)
        return kept

    risk_engine.enrich_signals = wrapped
    try:
        yield removed
    finally:
        risk_engine.enrich_signals = original


def _rs20_filter_summary(removed: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker = Counter(row["ticker"] for row in removed)
    by_strategy = Counter(row["strategy"] for row in removed)
    by_leader_state = Counter(str(row.get("rs20_entry_state_leader")) for row in removed)
    return {
        "removed_signal_count": len(removed),
        "removed_by_ticker": dict(sorted(by_ticker.items())),
        "removed_by_strategy": dict(sorted(by_strategy.items())),
        "removed_by_rs20_entry_state_leader": dict(sorted(by_leader_state.items())),
        "sample_removed": removed[:16],
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


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})

    by_window: dict[str, dict[str, Any]] = {}
    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        included = sorted(set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers)
        candidate_universe = sorted(set(core_universe) | set(included))

        core = _run_window(label, spec, core_universe, spec["baseline_snapshot"])
        before = _run_window(
            label,
            spec,
            candidate_universe,
            spec["candidate_snapshot"],
            scalar=RISK_SCALAR,
        )
        with _patched_space_rs20_leader_gate() as removed:
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
            "space_rs20_leader_filter": _rs20_filter_summary(removed),
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
    before_space_attr = _aggregate_space_attr(
        {
            label: {
                "space_trade_attribution": row["before_space_trade_attribution"]
            }
            for label, row in by_window.items()
        }
    )
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

    if gate["passed"]:
        decision = "accepted_default_off_rs20_leader_refinement"
        rejection_reason = None
        interpretation = (
            "The accepted official-catalyst Space sleeve improves when entries "
            "also carry the existing RS20 entry-state leader flag. This refines "
            "the default-off forward hypothesis only; live slots remain zero "
            "until shared production policy and forward evidence pass."
        )
    else:
        decision = "rejected_rs20_leader_refinement"
        rejection_reason = (
            "Requiring the existing RS20 entry-state leader flag did not beat the "
            "accepted exp-20260511-011 0.75x Space official-catalyst hypothesis "
            "under the pre-registered three-window gate."
        )
        interpretation = (
            "RS20 leadership is useful as a broad core sizing feature, but it is "
            "not sufficient as a Space sleeve entry gate on the frozen official "
            "catalyst sample. Keep the accepted 0.75x hypothesis unchanged."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Space official-catalyst entries may have better risk-adjusted EV "
            "when they also show the accepted broad RS20 entry-state leadership "
            "condition before sizing."
        ),
        "change_type": "entry_qualification_shadow_replay",
        "changed_variable": "space_official_catalyst_requires_rs20_entry_state_leader",
        "single_causal_variable": "space_official_catalyst_rs20_entry_state_leader_requirement",
        "parameters": {
            "candidate_pool_source": "exp-20260511-010",
            "before_hypothesis_source": "exp-20260511-011",
            "candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "risk_scalar": RISK_SCALAR,
            "rs20_definition_source": "risk_engine.rs20_entry_state_leader using accepted shared threshold",
            "rs20_threshold_changed": False,
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "space risk scalar 0.75",
                "RS20 threshold and broad RS20 sizing top-up",
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
            "official-catalyst 0.75x; after uses the same pool/scalar but filters "
            "only Space entries that lack the existing rs20_entry_state_leader flag."
        ),
        "core_baseline_metrics": core_metrics,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window_vs_before": delta_vs_before,
            "by_window_vs_core": delta_vs_core,
            "aggregate_vs_before": gate["aggregate_delta_vs_before"],
            "aggregate_vs_core": gate["aggregate_delta_vs_core"],
        },
        "expected_value_score_delta": gate["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "core_aggregate": core_agg,
        "before_aggregate": before_agg,
        "after_aggregate": after_agg,
        "gate_questions": {
            "alpha_hypothesis": (
                "entry qualification / risk allocation: official Space catalysts "
                "need the existing RS20 entry-state leader flag."
            ),
            "prior_similar_experiments": [
                "exp-20260511-010 locked official-catalyst membership and rejected full risk on drawdown.",
                "exp-20260511-011 accepted the same membership at 0.75x default-off risk.",
                "exp-20260511-012 rejected trend-only filtering.",
                "exp-20260511-014 rejected blanket no-add-on lifecycle.",
                "exp-20260511-015 rejected breakout risk-distance caps.",
                "No prior Space experiment isolated the existing RS20 entry-state leader flag.",
            ],
            "single_causal_variable": "Space official-catalyst RS20 leader requirement.",
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp-20260511-011, improve at "
                "least 2/3 EV windows versus that hypothesis, stay positive in all "
                "windows versus core, avoid drawdown worsening versus exp-20260511-011, "
                "keep drawdown damage versus core <= 2 pp, survival >= 5%, and keep "
                "Space positive-contribution concentration within guard."
            ),
            "reproducibility": (
                "This script reruns core, accepted Space 0.75x, and the RS20-leader "
                "variant across the three docs/backtesting.md snapshots."
            ),
        },
        "gate_results": {
            "gate1": {
                "core_baseline_metrics": core_metrics,
                "before_hypothesis_metrics": before_metrics,
            },
            "gate2": open_position_audit,
            "gate3": {
                "new_filter_added": True,
                "scope": "Space official-catalyst sleeve only; core filters unchanged",
                "minimum_after_survival_rate": after_agg.get("min_survival_rate"),
                "passed": after_agg.get("min_survival_rate", 0.0) >= 0.05,
            },
            "gate4": gate,
        },
        "space_trade_attribution": {
            "before": before_space_attr,
            "after": after_space_attr,
        },
        "by_window": by_window,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "Space event-state forward data is still below the closed-decision "
                "gate; this tests an existing deterministic entry-state feature."
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
            "Keep exp-20260511-011 official-catalyst 0.75x unchanged unless this refinement passes and is implemented as shared production-visible policy.",
            "Do not retry nearby RS20 thresholds or scalars on the same frozen Space sample.",
            "Collect forward official-catalyst replacement value by RS20 leader bucket.",
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
        "title": "Space official-catalyst RS20 leader gate",
        "status": payload["decision"],
        "lane": "alpha_search",
        "single_causal_variable": payload["single_causal_variable"],
        "result": {
            "decision": payload["decision"],
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
    for label, row in payload["by_window"].items():
        rows.append(
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
                removed=row["space_rs20_leader_filter"]["removed_signal_count"],
            )
        )

    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(
        "\n".join(
            [
                f"# {EXPERIMENT_ID} Space Official-Catalyst RS20 Leader Gate",
                "",
                f"Decision: `{payload['decision']}`.",
                "",
                "Hypothesis: keep the accepted official-catalyst Space pool and "
                "0.75x risk budget, but require the existing `rs20_entry_state_leader` "
                "flag for Space entries.",
                "",
                "| Window | Before EV | After EV | dEV vs before | dEV vs core | "
                "Before PnL | After PnL | dPnL | Removed Space signals |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                *rows,
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
        f"\nLatest Space RS20 refinement: `{EXPERIMENT_ID}` tested whether the "
        "accepted official-catalyst Space 0.75x forward hypothesis should require "
        "the existing `rs20_entry_state_leader` flag. The result was "
        f"`{payload['decision']}`: aggregate EV delta versus exp-20260511-011 "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}`, "
        f"aggregate PnL delta "
        f"`$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}`. "
        "Keep the official-catalyst 0.75x hypothesis unchanged unless forward "
        "RS20-bucket replacement value says otherwise.\n"
    )
    _append_once(CURRENT_STATE_MD, f"Latest Space RS20 refinement: `{EXPERIMENT_ID}`", state_note)

    playbook_note = (
        f"\n### 2026-05-11 mechanism update: Space RS20 leader refinement\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: requiring the accepted shared `rs20_entry_state_leader` flag "
        "inside the accepted Space official-catalyst 0.75x sleeve changed the "
        f"forward hypothesis by aggregate EV "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}` "
        f"and PnL `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}` "
        "versus exp-20260511-011.\n\n"
        "Mechanism insight: do not retune RS20 thresholds or scalars on the frozen "
        "Space sleeve. Treat RS20 as a forward attribution bucket for official "
        "catalysts unless this exact deterministic gate passes and is implemented "
        "as shared production-visible policy.\n"
    )
    _append_once(
        PLAYBOOK_MD,
        "### 2026-05-11 mechanism update: Space RS20 leader refinement",
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
                "aggregate_delta_vs_before": payload["delta_metrics"]["aggregate_vs_before"],
                "aggregate_delta_vs_core": payload["delta_metrics"]["aggregate_vs_core"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
