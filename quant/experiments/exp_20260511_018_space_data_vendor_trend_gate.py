"""exp-20260511-018: Space data-vendor trend-only refinement.

The accepted Space forward hypothesis is the official-catalyst operating
subpool at 0.75x risk. This experiment changes one quality variable inside
that sleeve: pure earth-observation / data-vendor names must be trend_long
entries, while launch, connectivity, lunar, and manufacturing names keep the
accepted strategy mix.
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


EXPERIMENT_ID = "exp-20260511-018"
STEM = "space_data_vendor_trend_gate"
RISK_SCALAR = 0.75
DATA_VENDOR_TICKERS = ("PL", "BKSY")
ALLOWED_DATA_VENDOR_STRATEGIES = ("trend_long",)
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


@contextmanager
def _patched_space_data_vendor_strategy_gate():
    import signal_engine  # noqa: PLC0415

    original = signal_engine.generate_signals
    data_vendors = {ticker.upper() for ticker in DATA_VENDOR_TICKERS}
    allowed = {strategy.lower() for strategy in ALLOWED_DATA_VENDOR_STRATEGIES}
    removed: list[dict[str, Any]] = []

    def wrapped(features_dict, *args, **kwargs):
        signals = original(features_dict, *args, **kwargs)
        kept = []
        for sig in signals:
            ticker = str(sig.get("ticker") or "").upper()
            strategy = str(sig.get("strategy") or "").lower()
            if ticker in data_vendors and strategy not in allowed:
                removed.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy or "unknown",
                        "entry_price": _round(sig.get("entry_price"), 4),
                        "confidence_score": _round(sig.get("confidence_score"), 4),
                        "trade_quality_score": _round(sig.get("trade_quality_score"), 4),
                        "risk_reward_ratio": _round(sig.get("risk_reward_ratio"), 4),
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
    by_strategy = Counter(row["strategy"] for row in removed)
    return {
        "removed_signal_count": len(removed),
        "removed_by_ticker": dict(sorted(by_ticker.items())),
        "removed_by_strategy": dict(sorted(by_strategy.items())),
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
        1
        for delta in delta_vs_before.values()
        if delta.get("expected_value_score", 0.0) > 0
    )
    ev_regressed_vs_before = sum(
        1
        for delta in delta_vs_before.values()
        if delta.get("expected_value_score", 0.0) < 0
    )
    ev_improved_vs_core = sum(
        1
        for delta in delta_vs_core.values()
        if delta.get("expected_value_score", 0.0) > 0
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
        with _patched_space_data_vendor_strategy_gate() as removed:
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
            "data_vendor_tickers": sorted(set(DATA_VENDOR_TICKERS) & set(included)),
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
            "space_data_vendor_strategy_filter": _filter_summary(removed),
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
        decision = "accepted_default_off_data_vendor_trend_gate"
        rejection_reason = None
        interpretation = (
            "The accepted Space official-catalyst sleeve improves when pure "
            "earth-observation/data-vendor entries are trend-only, while launch, "
            "connectivity, lunar, and manufacturing names keep the accepted "
            "strategy mix. This refines the default-off forward hypothesis only; "
            "live Space slots remain zero."
        )
    else:
        decision = "rejected_data_vendor_trend_gate"
        rejection_reason = (
            "The PL/BKSY trend-only data-vendor gate did not beat the accepted "
            "exp-20260511-011 0.75x Space official-catalyst hypothesis under the "
            "pre-registered three-window gate."
        )
        interpretation = (
            "Data-vendor strategy qualification is not strong enough to replace "
            "the accepted Space official-catalyst 0.75x hypothesis."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Within the accepted official-catalyst Space sleeve, earth-observation/"
            "data-vendor names should require trend confirmation; their contract "
            "and revenue-quality catalysts are less suited to raw breakout entries "
            "than launch, connectivity, lunar, or manufacturing names."
        ),
        "change_type": "entry_qualification_shadow_replay",
        "changed_variable": "space_data_vendor_allowed_strategy_family",
        "single_causal_variable": "space_data_vendor_allowed_strategy_family",
        "parameters": {
            "candidate_pool_source": "exp-20260511-010",
            "before_hypothesis_source": "exp-20260511-011",
            "official_candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "data_vendor_tickers": list(DATA_VENDOR_TICKERS),
            "allowed_data_vendor_strategies": list(ALLOWED_DATA_VENDOR_STRATEGIES),
            "risk_scalar": RISK_SCALAR,
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "space risk scalar 0.75",
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
            "official-catalyst 0.75x; after uses the same pool/scalar but filters "
            "PL/BKSY Space entries to trend_long only."
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
                "entry qualification: Space data vendors require trend_long inside "
                "the accepted official-catalyst 0.75x sleeve."
            ),
            "prior_similar_experiments": [
                "exp-20260511-011 accepted the official-catalyst 0.75x default-off hypothesis.",
                "exp-20260511-012 rejected a blanket trend-only Space refinement.",
                "exp-20260511-014 rejected a blanket no-add-on Space lifecycle refinement.",
                "exp-20260511-015 rejected breakout risk-distance caps.",
                "exp-20260511-016 found RS20 leader gating inert.",
                "No prior Space experiment isolated the earth-observation/data-vendor strategy family.",
            ],
            "single_causal_variable": "allowed strategy family for PL/BKSY only.",
            "acceptance_standard": (
                "Must improve aggregate EV/PnL versus exp-20260511-011, improve "
                "at least 2/3 EV windows versus that hypothesis, stay EV-positive "
                "in all windows versus core, keep drawdown damage versus core <= 2 pp, "
                "survival >= 5%, and keep Space positive-contribution concentration within guard."
            ),
            "reproducibility": (
                "This script reruns core, accepted Space 0.75x, and the PL/BKSY "
                "trend-only variant across the three docs/backtesting.md snapshots."
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
                "scope": "Space official-catalyst PL/BKSY sleeve only; core filters unchanged",
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
                "gate; this tests a deterministic subsegment strategy discriminator."
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
            "If accepted, promote only as a shared production-visible default-off forward hypothesis; live slots remain zero.",
            "Do not generalize this to all Space breakout entries; exp-20260511-012 already rejected blanket trend-only.",
            "Collect forward replacement value separately for data-vendor and hardware/network buckets.",
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
        "title": "Space data-vendor trend gate",
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
                removed=row["space_data_vendor_strategy_filter"]["removed_signal_count"],
            )
        )

    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(
        "\n".join(
            [
                f"# {EXPERIMENT_ID} Space Data-Vendor Trend Gate",
                "",
                f"Decision: `{payload['decision']}`.",
                "",
                "Hypothesis: keep the accepted official-catalyst Space pool and "
                "0.75x risk budget, but allow PL/BKSY entries only when they are "
                "`trend_long`.",
                "",
                "| Window | Before EV | After EV | dEV vs before | dEV vs core | "
                "Before PnL | After PnL | dPnL | Removed data-vendor signals |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                *rows,
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
        ),
        encoding="utf-8",
    )

    state_note = (
        f"\nLatest Space data-vendor refinement: `{EXPERIMENT_ID}` tested whether "
        "the accepted official-catalyst Space 0.75x forward hypothesis should "
        "allow PL/BKSY only as `trend_long` entries. The result was "
        f"`{payload['decision']}`: aggregate EV delta versus exp-20260511-011 "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}`, "
        f"aggregate PnL delta "
        f"`$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}`. "
        "Do not generalize this to all Space breakout entries; keep it scoped "
        "to the data-vendor subsegment.\n"
    )
    _append_once(
        CURRENT_STATE_MD,
        f"Latest Space data-vendor refinement: `{EXPERIMENT_ID}`",
        state_note,
    )

    playbook_note = (
        f"\n### 2026-05-11 mechanism update: Space data-vendor trend gate\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: requiring PL/BKSY, the earth-observation/data-vendor part of "
        "the accepted official-catalyst Space sleeve, to be `trend_long` only "
        "changed the accepted 0.75x forward hypothesis by aggregate EV "
        f"`{payload['delta_metrics']['aggregate_vs_before'].get('expected_value_score_sum'):+.4f}` "
        f"and PnL `$"
        f"{payload['delta_metrics']['aggregate_vs_before'].get('total_pnl_sum'):+,.2f}` "
        "versus exp-20260511-011.\n\n"
        "Mechanism insight: Space refinement should be by catalyst/economic "
        "bucket, not blanket strategy family. Pure data-vendor breakouts are a "
        "different mechanism from launch, network, lunar, and manufacturing "
        "convexity; future forward attribution should keep those buckets separate.\n"
    )
    _append_once(
        PLAYBOOK_MD,
        "### 2026-05-11 mechanism update: Space data-vendor trend gate",
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
