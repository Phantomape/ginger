"""
Retests the forward-qualified mature-satcom Space candidate extension on the
current accepted Space stack through exp-20260515-024.

This changes one candidate-pool variable: add only satcom extension tickers
whose mature 5d ledger profile is positive versus cash, same-theme replacement,
SPY, QQQ, UFO, and ARKX, and admit those added tickers only for trend_long
signals. It does not change exits, ranking, stops, LLM authority, or live Space
slots.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260515_013_space_fast_5d_satcom_candidate_pool as exp013
import exp_20260515_015_space_fast_5d_satcom_trend_only_pool as exp015
import exp_20260515_021_space_defense_budget_same_theme_winner_trend_risk as exp021
import exp_20260515_024_space_source_diversity_peer_nonleader_trend_risk as exp024


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260515-029"
STEM = "space_current_stack_fast_5d_satcom_trend_pool"
BEFORE_EXPERIMENT_ID = "exp-20260515-024"
BEFORE_STEM = "space_source_diversity_peer_nonleader_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR = 1.025
TARGET_STRATEGY = "trend_long"
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005


def _safe(value: Any) -> Any:
    return exp013._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _collect_gates_with_pool(tickers: tuple[str, ...]) -> dict[str, Any]:
    with exp013._official_space_pool(tickers):
        gates = exp021._collect_gates()
    gates["official_space_pool"] = list(tickers)
    gates["satcom_fast_5d_candidate_gate"] = exp013._satcom_fast_5d_gate()
    return gates


def _run_stack_with_pool(
    label: str,
    *,
    tickers: tuple[str, ...],
    gates: dict[str, Any],
    added_tickers: tuple[str, ...] = (),
) -> dict[str, Any]:
    trend_filter_summary: dict[str, Any] | None = None
    with exp013._official_space_pool(tickers):
        if added_tickers:
            with exp015._trend_only_extension_scope(added_tickers) as scope:
                variant = exp024._run_exp021_stack_variant(
                    label,
                    peer_nonleader_scalar=(
                        ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR
                    ),
                    gates=gates,
                )
            records = list(scope["records"])
            by_window: dict[str, dict[str, Any]] = {}
            for record in records:
                window = record.get("window") or "unknown"
                row = by_window.setdefault(
                    window,
                    {"count": 0, "tickers": {}, "strategies": {}},
                )
                row["count"] += 1
                ticker = str(record.get("ticker") or "")
                strategy = str(record.get("strategy") or "unknown")
                row["tickers"][ticker] = int(row["tickers"].get(ticker, 0)) + 1
                row["strategies"][strategy] = int(row["strategies"].get(strategy, 0)) + 1
            trend_filter_summary = {
                "counts": dict(sorted(scope["counts"].items())),
                "records": records,
                "by_window": by_window,
            }
        else:
            variant = exp024._run_exp021_stack_variant(
                label,
                peer_nonleader_scalar=ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR,
                gates=gates,
            )

    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "official_space_pool": list(tickers),
        "satcom_fast_5d_added_tickers": list(added_tickers),
        "satcom_fast_5d_added_strategy_scope": TARGET_STRATEGY
        if added_tickers
        else None,
        "accepted_source_diversity_peer_nonleader_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR
        ),
    }
    if trend_filter_summary is not None:
        variant["satcom_trend_only_extension_filter"] = trend_filter_summary
    return variant


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return exp024.exp041.source_diversity_exp._aggregate_delta(
        after["aggregate"],
        before["aggregate"],
    )


def _by_window_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        label: exp024.exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in after["by_window"].items()
    }


def _space_trades_by_extension(
    variant: dict[str, Any],
    added_tickers: tuple[str, ...],
) -> dict[str, Any]:
    return exp015._space_trades_by_extension(variant, added_tickers)


def _gate(
    after: dict[str, Any],
    before: dict[str, Any],
    *,
    added_tickers: tuple[str, ...],
) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(after, before)
    by_window_delta = _by_window_delta(after, before)
    ev_improved = {
        label: row["expected_value_score"]
        for label, row in by_window_delta.items()
        if row["expected_value_score"] > 1e-9
    }
    ev_regressed = {
        label: row["expected_value_score"]
        for label, row in by_window_delta.items()
        if row["expected_value_score"] < -1e-9
    }
    extension_trade_attribution = _space_trades_by_extension(after, added_tickers)
    extension_trade_count = sum(
        row["trade_count"] for row in extension_trade_attribution.values()
    )
    non_trend_filtered_count = int(
        (
            after.get("satcom_trend_only_extension_filter")
            or {}
        ).get("counts", {}).get("filtered_extension_signal", 0)
    )
    passed = bool(
        extension_trade_count > 0
        and aggregate_delta["expected_value_score_sum"] > 0.0
        and aggregate_delta["total_pnl_sum"] > 0.0
        and len(ev_improved) >= 2
        and not ev_regressed
        and aggregate_delta["max_drawdown_pct_max"] <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
        and after["aggregate"].get("min_survival_rate", 0.0) >= MIN_SURVIVAL_RATE
        and after["aggregate"].get("trade_count_sum", 0) >= MIN_TRADE_COUNT
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "passed": passed,
        "improved_windows": ev_improved,
        "regressed_windows": ev_regressed,
        "extension_trade_attribution": extension_trade_attribution,
        "extension_trade_count": extension_trade_count,
        "non_trend_filtered_extension_signal_count": non_trend_filtered_count,
        "reasons": {
            "extension_trades_present": extension_trade_count > 0,
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"]
            > 0.0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0.0,
            "at_least_two_windows_improved": len(ev_improved) >= 2,
            "no_window_regressed": not ev_regressed,
            "drawdown_delta_within_limit": (
                aggregate_delta["max_drawdown_pct_max"]
                <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            ),
            "survival_rate_ok": after["aggregate"].get("min_survival_rate", 0.0)
            >= MIN_SURVIVAL_RATE,
            "trade_count_ok": after["aggregate"].get("trade_count_sum", 0)
            >= MIN_TRADE_COUNT,
        },
    }


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = ("worst_trade_pct", "max_consecutive_losses", "tail_loss_share")
    return {
        label: {key: row["metrics"].get(key) for key in keys}
        for label, row in variant["by_window"].items()
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    promoted = payload["decision"] == "accept"
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_fast_5d_satcom_trend_only_pool_membership",
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "base_official_space_pool": payload["base_official_space_pool"],
            "added_tickers": payload["added_tickers"],
            "candidate_universe": list(exp013.SATCOM_EXTENSION_CANDIDATES),
            "forward_horizon": exp013.FORWARD_HORIZON,
            "allowed_strategy_for_added_tickers": TARGET_STRATEGY,
            "satcom_fast_5d_gate": payload["satcom_fast_5d_gate"],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in exp024.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": after["aggregate"],
        "by_window_before_metrics": {
            label: row["metrics"] for label, row in before["by_window"].items()
        },
        "by_window_after_metrics": {
            label: row["metrics"] for label, row in after["by_window"].items()
        },
        "by_window_delta": gate["by_window_delta_vs_before"],
        "expected_value_score_delta": gate["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "total_pnl_delta": gate["aggregate_delta_vs_before"]["total_pnl_sum"],
        "risk_distribution": {
            "before": _risk_distribution(before),
            "after": _risk_distribution(after),
        },
        "extension_trade_attribution": gate["extension_trade_attribution"],
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Candidate-pool alpha: forward-qualified mature satcom tickers "
                "with all-positive 5d replacement evidence may add trend "
                "continuation value to the current accepted Space stack."
            ),
            "2_prior_similar_experiments": [
                "exp-20260511-026 rejected broad mature-satcom breadth because only one window improved versus before.",
                "exp-20260515-013 rejected fast-5d satcom pool on exp-20260514-053 because old_thin regressed.",
                "exp-20260515-015 rejected trend-only fast-5d satcom pool on exp-20260514-053 for the same old_thin regression.",
                "This run retests the stricter trend-only forward-qualified satcom pool on the current accepted exp-20260515-024 Space stack, not the old exp053 stack.",
            ],
            "3_single_causal_variable": (
                "Only current-stack fast-5d satcom trend-only candidate membership changes."
            ),
            "4_success_criteria": (
                "Extension trades present, aggregate EV/PnL positive, at least "
                "two EV-improved windows, no EV-regressed windows, max drawdown "
                "drift <= 0.5 pp, survival >= 5%, and trade count >= 50."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260515_029_space_current_stack_fast_5d_satcom_trend_pool.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: current-stack fast-5d satcom trend-only candidate "
            "membership did not improve the fixed three-window protocol without "
            "regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry IRDM/VSAT trend-only admission on these frozen "
            "windows without new closed forward rows or a materially different "
            "production-visible event-quality discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, added membership and trend-only scope must live in "
                "shared space_catalyst_sleeve.py and daily observe-only paths; "
                "live Space slots remain zero."
                if promoted
                else "Experiment-only official-pool monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "The prior same-theme laggard run had zero runtime coverage, LLM "
            "soft-ranking remains data-limited, and broad ARKX/UFO admission "
            "was harmful. This tests a narrower mature-cohort expansion with "
            "forward replacement evidence rather than adding noisy tickers."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space current-stack fast-5d satcom trend pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_fast_5d_satcom_trend_only_pool_membership` on top of "
            f"accepted `{BEFORE_EXPERIMENT_ID}`."
        ),
        "",
        "## Gate 1 Baseline",
        f"- before experiment: `{BEFORE_EXPERIMENT_ID}` / `{BEFORE_STEM}`",
        f"- aggregate before EV: `{before['aggregate']['expected_value_score_sum']}`",
        f"- aggregate before PnL: `{before['aggregate']['total_pnl_sum']}`",
        f"- aggregate before max drawdown pct max: `{before['aggregate']['max_drawdown_pct_max']}`",
        "",
        "## Gate 2 Field Check",
        f"- open position field check passed: `{payload['field_check']['passed']}`",
        f"- satcom fast-5d gate passed: `{payload['satcom_fast_5d_gate']['passed']}`",
        f"- added tickers: `{payload['added_tickers']}`",
        f"- allowed strategy for added tickers: `{TARGET_STRATEGY}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{after['aggregate']['min_survival_rate']}`",
        "- no core filter was added; this is default-off Space candidate-scope membership.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after | extension trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = after["by_window"][label]["metrics"]
        extension = gate["extension_trade_attribution"][label]["trade_count"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} | {extension} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
                extension=extension,
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
            f"- extension trades: `{gate['extension_trade_count']}`",
            f"- non-trend extension signals filtered: `{gate['non_trend_filtered_extension_signal_count']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(promoted).lower()}",
            f"  backtester_adapter_changed: {str(promoted).lower()}",
            f"  run_adapter_changed: {str(promoted).lower()}",
            f"  replay_only: {str(not promoted).lower()}",
            f"  parity_test_added: {str(promoted).lower()}",
            "  live_slots: 0",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload["gate_results"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Current-stack fast-5d satcom trend pool "
            f"{payload['decision']} with EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    completed_at = datetime.now(timezone.utc).isoformat()
    base_pool = tuple(exp024.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)
    satcom_gate = exp013._satcom_fast_5d_gate()
    added = tuple(
        ticker for ticker in satcom_gate["target_tickers"] if ticker not in base_pool
    )
    extended_pool = tuple(sorted(set(base_pool) | set(added)))

    base_gates = _collect_gates_with_pool(base_pool)
    extended_gates = _collect_gates_with_pool(extended_pool)
    before = _run_stack_with_pool(
        "accepted_exp024_base_pool",
        tickers=base_pool,
        gates=base_gates,
    )
    after = _run_stack_with_pool(
        "current_stack_fast_5d_satcom_trend_pool",
        tickers=extended_pool,
        gates=extended_gates,
        added_tickers=added,
    )
    gate = _gate(after, before, added_tickers=added)
    field_check = exp021.exp051._open_position_field_check()
    decision = (
        "accept"
        if field_check["passed"] and satcom_gate["passed"] and gate["passed"]
        else "reject"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "Forward-qualified mature satcom tickers with all-positive 5d "
            "replacement evidence may add Space trend continuation value to "
            "the current accepted stack without broad noisy ticker admission."
        ),
        "base_official_space_pool": list(base_pool),
        "extended_official_space_pool": list(extended_pool),
        "added_tickers": list(added),
        "base_gates": base_gates,
        "extended_gates": extended_gates,
        "satcom_fast_5d_gate": satcom_gate,
        "field_check": field_check,
        "before_variant": before,
        "after_variant": after,
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "changed_variable": "space_fast_5d_satcom_trend_only_pool_membership",
    }
    payload["experiment_log_record"] = _experiment_record(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{EXPERIMENT_ID}.json", _ticket(payload))
    artifact_path = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    payload = run()
    persist(payload)
    gate = payload["gate_results"]
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "added_tickers": payload["added_tickers"],
                    "extension_trades": gate["extension_trade_count"],
                    "non_trend_filtered_extension_signals": gate[
                        "non_trend_filtered_extension_signal_count"
                    ],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "improved_windows": gate["improved_windows"],
                    "regressed_windows": gate["regressed_windows"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
