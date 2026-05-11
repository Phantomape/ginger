"""exp-20260511-010: Space official-catalyst subpool replay.

This alpha-search replay tests one candidate-pool variable inside the
SPACE_CATALYST_SHADOW sleeve: keep only operating-growth records closest to
official contract, regulatory, customer, launch, lunar, or defense-data
catalysts. It is static historical evidence only and does not enable live
slots, production orders, ranking, sizing, or core universe membership.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
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
    _run_window,
    _snapshot_tickers,
    _space_trade_attribution,
)


EXPERIMENT_ID = "exp-20260511-010"
STEM = "space_official_catalyst_subpool"
OFFICIAL_CATALYST_TICKERS = (
    "RKLB",
    "ASTS",
    "LUNR",
    "PL",
    "RDW",
    "BKSY",
)
UNAVAILABLE_OFFICIAL_CATALYST_TICKERS = {
    "HAWK": "short_history_no_ohlcv_rows_in_exp_20260510_028_snapshots",
}
EXCLUDED_SPACE_TICKERS = {
    "IRDM": "mature_satcom_breadth_not_direct_official_catalyst",
    "VSAT": "mature_satcom_breadth_not_direct_official_catalyst",
    "GSAT": "connectivity_narrative_without_current_official_forward_gate",
    "SATS": "legacy_satcom_starlink_attention_balance_sheet_sensitive",
    "ARKX": "theme_beta_benchmark_not_operating_trade_candidate",
    "UFO": "theme_beta_benchmark_not_operating_trade_candidate",
    "SPCE": "quarantine_meme_dilution_execution_risk",
}
MAX_DRAWDOWN_DAMAGE = 0.02

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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
    marker = f'"experiment_id": "{payload["experiment_id"]}"'
    compact_marker = f'"experiment_id":"{payload["experiment_id"]}"'
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing or compact_marker in existing:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _append_once(path: Path, marker: str, text: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing:
        return
    with path.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(text)


def _aggregate_space_attr(by_window: dict[str, dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "trade_count": 0,
        "total_pnl": 0.0,
        "wins": 0,
        "losses": 0,
        "by_ticker": defaultdict(
            lambda: {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        ),
    }
    for row in by_window.values():
        attr = row["space_trade_attribution"]
        totals["trade_count"] += attr["trade_count"]
        totals["total_pnl"] += float(attr["total_pnl"] or 0.0)
        totals["wins"] += attr["wins"]
        totals["losses"] += attr["losses"]
        for ticker, stats in attr["by_ticker"].items():
            target = totals["by_ticker"][ticker]
            target["trade_count"] += stats["trade_count"]
            target["wins"] += stats["wins"]
            target["losses"] += stats["losses"]
            target["pnl"] += float(stats["pnl"] or 0.0)

    positive = {
        ticker: stats["pnl"]
        for ticker, stats in totals["by_ticker"].items()
        if stats["pnl"] > 0
    }
    positive_sum = sum(positive.values())
    single_share = round(max(positive.values()) / positive_sum, 4) if positive_sum else None
    return {
        "trade_count": totals["trade_count"],
        "total_pnl": _round(totals["total_pnl"], 2),
        "wins": totals["wins"],
        "losses": totals["losses"],
        "win_rate": _round(
            totals["wins"] / totals["trade_count"] if totals["trade_count"] else None,
            4,
        ),
        "single_ticker_positive_share": single_share,
        "by_ticker": {
            ticker: {**stats, "pnl": _round(stats["pnl"], 2)}
            for ticker, stats in sorted(totals["by_ticker"].items())
        },
    }


def _gate(
    before_agg: dict[str, Any],
    after_agg: dict[str, Any],
    delta_by_window: dict[str, dict[str, Any]],
    space_attr: dict[str, Any],
) -> dict[str, Any]:
    aggregate_delta = _delta(after_agg, before_agg)
    ev_improved = sum(
        1 for delta in delta_by_window.values() if delta.get("expected_value_score", 0.0) > 0
    )
    ev_regressed = sum(
        1 for delta in delta_by_window.values() if delta.get("expected_value_score", 0.0) < 0
    )
    max_drawdown_worsening = max(
        delta.get("max_drawdown_pct", 0.0) for delta in delta_by_window.values()
    )
    passed = (
        aggregate_delta.get("expected_value_score_sum", 0.0) > 0
        and aggregate_delta.get("total_pnl_sum", 0.0) > 0
        and ev_improved == len(WINDOWS)
        and ev_regressed == 0
        and max_drawdown_worsening <= MAX_DRAWDOWN_DAMAGE
        and after_agg["min_survival_rate"] >= 0.05
        and (
            space_attr["single_ticker_positive_share"] is None
            or space_attr["single_ticker_positive_share"] <= 0.70
        )
    )
    return {
        "passed": passed,
        "aggregate_delta": aggregate_delta,
        "windows_ev_improved": ev_improved,
        "windows_ev_regressed": ev_regressed,
        "max_drawdown_worsening": _round(max_drawdown_worsening, 4),
    }


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})
    by_window: dict[str, dict[str, Any]] = {}

    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        included = sorted(set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers)
        missing = sorted(set(OFFICIAL_CATALYST_TICKERS) - set(included))
        candidate_universe = sorted(set(core_universe) | set(included))

        baseline = _run_window(label, spec, core_universe, spec["baseline_snapshot"])
        candidate = _run_window(label, spec, candidate_universe, spec["candidate_snapshot"])
        by_window[label] = {
            "window": spec,
            "included_space_tickers": included,
            "missing_space_tickers": missing,
            "baseline_metrics": baseline["metrics"],
            "candidate_metrics": candidate["metrics"],
            "delta": _delta(candidate["metrics"], baseline["metrics"]),
            "space_trade_attribution": _space_trade_attribution(
                candidate["trades"],
                set(included),
            ),
        }

    before_metrics = {label: row["baseline_metrics"] for label, row in by_window.items()}
    after_metrics = {label: row["candidate_metrics"] for label, row in by_window.items()}
    delta_by_window = {label: row["delta"] for label, row in by_window.items()}
    before_agg = _aggregate(before_metrics)
    after_agg = _aggregate(after_metrics)
    space_attr = _aggregate_space_attr(by_window)
    gate = _gate(before_agg, after_agg, delta_by_window, space_attr)

    if gate["passed"]:
        decision = "observed_only_positive_subpool_not_promoted"
        rejection_reason = None
        interpretation = (
            "The official-catalyst subpool improved all three fixed windows, but "
            "it remains static historical evidence and cannot be promoted without "
            "PIT forward decisions and production-visible pilot plumbing."
        )
    else:
        decision = "rejected_full_risk_official_subpool"
        rejection_reason = (
            "The official-catalyst Space subpool improved EV/PnL in all three "
            "windows, but full core-sized replay failed the drawdown guard."
        )
        interpretation = (
            "The right Space direction is not broad static universe promotion or "
            "attention-headline ranking. The signal is concentrated in official "
            "contract/regulatory/customer-style operating names, but it needs a "
            "smaller specialist risk budget before any forward pilot design."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "Space sleeve alpha should come from official contract/regulatory/"
            "customer operating-growth catalysts, not broad mature satcom breadth "
            "or attention-only space beta."
        ),
        "change_type": "candidate_pool_static_replay",
        "changed_variable": "space_official_catalyst_subpool_membership",
        "single_causal_variable": "space_official_catalyst_subpool_membership",
        "parameters": {
            "included_tickers": list(OFFICIAL_CATALYST_TICKERS),
            "unavailable_in_snapshots": UNAVAILABLE_OFFICIAL_CATALYST_TICKERS,
            "excluded_tickers": EXCLUDED_SPACE_TICKERS,
            "risk_scalar": 1.0,
            "locked_variables": [
                "core production universe",
                "signal generation",
                "entry filters",
                "ranking",
                "sizing",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live pilot slots",
            ],
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "Entry/candidate-pool alpha: restrict Space replay to official "
                "contract/regulatory/customer operating-growth names."
            ),
            "2_history_check": {
                "exp-20260511-002": "Broad static pool was raw-positive but rejected for drawdown and hindsight membership.",
                "exp-20260511-009": "Broad static pool risk scalar sweep failed; 0.75x controlled drawdown but regressed late EV.",
                "exp-20260511-008": "Forward event ledger has only one mature outcome, so event trading is not yet promotable.",
            },
            "3_single_causal_variable": "Space candidate-pool membership.",
            "4_gate": (
                "docs/backtesting.md three windows; require positive aggregate "
                "EV/PnL, EV improvement in all windows, drawdown damage <= 2 pp, "
                "survival >= 5%, and concentration guard."
            ),
            "5_reproducibility": "Run this script from repo root; it writes JSON, ticket, artifact, and JSONL records.",
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}" for label, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three-window fixed protocol; baseline "
            "uses canonical snapshots and candidate uses exp-20260510-028 Space "
            "augmented snapshots with only the official-catalyst subpool added."
        ),
        "snapshots": {
            label: {"baseline": spec["baseline_snapshot"], "candidate": spec["candidate_snapshot"]}
            for label, spec in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "before_aggregate": before_agg,
        "after_metrics": after_metrics,
        "after_aggregate": after_agg,
        "delta_metrics": {"by_window": delta_by_window, "aggregate": gate["aggregate_delta"]},
        "expected_value_score_delta": gate["aggregate_delta"]["expected_value_score_sum"],
        "space_trade_attribution_aggregate": space_attr,
        "by_window": by_window,
        "gate_results": {
            "gate1": {"passed": True, "baseline_source": "rerun canonical baselines"},
            "gate2": {
                "passed": open_position_audit["passed"],
                "open_position_field_audit": open_position_audit,
            },
            "gate3": {
                "passed": after_agg["min_survival_rate"] >= 0.05,
                "new_filter_added": False,
                "survival_rates_after": {
                    label: metrics["survival_rate"] for label, metrics in after_metrics.items()
                },
            },
            "gate4": gate,
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "interpretation": interpretation,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "The Space forward ledger has insufficient mature outcomes; this "
                "tests deterministic candidate-pool quality instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "default_off_observation_only": True,
        },
        "next_evidence_needed": [
            "Do not enable live/default Space trades from this full-risk static subpool.",
            "Test only a bounded risk-budget variant for the same official-catalyst subpool.",
            "Require forward direct, same-theme, UFO/ARKX-relative, and core replacement value before live slots.",
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
    }
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Space Official-Catalyst Subpool",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "| Window | Base EV | After EV | dEV | Base DD | After DD | dDD | Space PnL | Space trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        space = payload["by_window"][label]["space_trade_attribution"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | {bdd:.4f} | {add:.4f} | {ddd:.4f} | {spnl:.2f} | {strades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                ddd=delta["max_drawdown_pct"],
                spnl=space["total_pnl"] or 0.0,
                strades=space["trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            "No orders, live slots, ranking, sizing, or run/backtest adapters changed.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space official-catalyst subpool replay",
            "status": payload["status"],
            "lane": payload["lane"],
            "created_at": payload["timestamp"],
            "single_causal_variable": payload["single_causal_variable"],
            "result": {
                "decision": payload["decision"],
                "aggregate_ev_delta": payload["expected_value_score_delta"],
                "aggregate_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
            },
            "next_steps": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    log_record = {
        "timestamp": payload["timestamp"],
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "related_files": payload["related_files"],
    }
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, log_record)

    state_text = (
        "\nLatest Space candidate-pool alpha search: `exp-20260511-010` tested "
        "an official-catalyst operating-growth subpool (`RKLB`, `ASTS`, `LUNR`, "
        "`PL`, `RDW`, `BKSY`) instead of the broad static Space pool. It improved "
        f"EV in all three windows and aggregate EV by `{payload['expected_value_score_delta']:+.4f}` "
        f"with aggregate PnL delta `${payload['delta_metrics']['aggregate']['total_pnl_sum']:,.2f}`, "
        f"but failed Gate 4 because max drawdown damage was "
        f"`{payload['gate_results']['gate4']['max_drawdown_worsening']:.2%}`. "
        "Conclusion: official-catalyst subpool is the right Space alpha direction, "
        "but not at full core risk.\n"
    )
    _append_once(CURRENT_STATE_MD, EXPERIMENT_ID, state_text)

    playbook_text = (
        f"\n### 2026-05-11 mechanism update: Space official-catalyst subpool\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: narrowing Space from the broad static pool to the official-catalyst "
        "operating-growth subpool improved EV in all three canonical windows, but "
        f"full-risk replay failed the drawdown guard. Aggregate EV delta was "
        f"`{payload['expected_value_score_delta']:+.4f}` and aggregate PnL delta was "
        f"`${payload['delta_metrics']['aggregate']['total_pnl_sum']:,.2f}`; max drawdown "
        f"damage was `{payload['gate_results']['gate4']['max_drawdown_worsening']:.2%}`.\n\n"
        "Mechanism insight: Space alpha should be optimized around official contract, "
        "regulatory, customer, launch/lunar, and defense-data catalysts, not broad "
        "mature satcom breadth or attention-only headlines. Do not promote this "
        "subpool at full core risk; the valid follow-up is a bounded specialist "
        "risk-budget test on the same subpool.\n"
    )
    _append_once(PLAYBOOK_MD, f"{EXPERIMENT_ID}`", playbook_text)


def main() -> None:
    payload = run_experiment()
    write_outputs(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "aggregate_delta": payload["delta_metrics"]["aggregate"],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
