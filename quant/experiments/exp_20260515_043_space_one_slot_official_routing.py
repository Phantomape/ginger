"""exp-20260515-043: Space one-slot official routing.

Tests one capital-allocation/routing variable on top of the accepted
exp-20260515-024 Space stack: allow only the first already-ranked official
Space signal in each daily sizing batch to size. This mirrors the production
observation model's one blocked Space slot without changing tickers, exits,
hard filters, LLM authority, risk scalars, or live Space slots.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
QUANT_DIR = ROOT / "quant"
EXPERIMENTS_DIR = THIS.parent
for path in (str(ROOT), str(QUANT_DIR), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import portfolio_engine
import exp_20260514_051_space_defense_budget_delayed_benchmark_trend_risk as exp051
import exp_20260515_021_space_defense_budget_same_theme_winner_trend_risk as exp021
import exp_20260515_024_space_source_diversity_peer_nonleader_trend_risk as exp024


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260515-043"
STEM = "space_one_slot_official_routing"
BEFORE_EXPERIMENT_ID = "exp-20260515-024"
BEFORE_STEM = "space_source_diversity_peer_nonleader_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR = 1.025
OFFICIAL_SPACE_TICKERS = tuple(
    exp024.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS
)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(value: Any) -> Any:
    return exp051._safe(value)


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
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
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


def _window_for_date(date_text: str) -> str | None:
    if not date_text:
        return None
    for label, spec in exp024.exp041.source_diversity_exp.WINDOWS.items():
        if str(spec["start"]) <= date_text <= str(spec["end"]):
            return label
    return None


def _record_signal(signal: dict[str, Any], action: str, reason: str) -> dict[str, Any]:
    date_text = str(signal.get("date") or "")[:10]
    return {
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": signal.get("strategy"),
        "date": date_text,
        "window": _window_for_date(date_text),
        "action": action,
        "reason": reason,
        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
        "trade_quality_score": signal.get("trade_quality_score"),
        "confidence_score": signal.get("confidence_score"),
        "space_source_diversity_peer_nonleader_trend_bucket": signal.get(
            "space_source_diversity_peer_nonleader_trend_bucket"
        ),
        "space_defense_budget_same_theme_winner_bucket": signal.get(
            "space_defense_budget_same_theme_winner_bucket"
        ),
    }


@contextmanager
def _one_slot_official_space_scope():
    """Keep only the first already-ranked official Space signal per sizing batch."""
    original_size_signals = portfolio_engine.size_signals
    official = {ticker.upper() for ticker in OFFICIAL_SPACE_TICKERS}
    counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []

    def size_one_slot_official_space(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        official_seen = False
        kept: list[dict[str, Any]] = []
        official_count = sum(
            1
            for signal in signals
            if str(signal.get("ticker") or "").upper() in official
        )
        if official_count:
            counts["sizing_batches_with_official_space_signal"] += 1
            counts["official_space_signals_seen"] += official_count
            counts[f"official_space_batch_size_{official_count}"] += 1

        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in official:
                kept.append(signal)
                continue
            if not official_seen:
                official_seen = True
                counts["kept_official_space_signal"] += 1
                counts[f"kept_{ticker}"] += 1
                records.append(
                    _record_signal(
                        signal,
                        action="kept",
                        reason="first_already_ranked_official_space_signal",
                    )
                )
                kept.append(signal)
                continue
            counts["filtered_official_space_signal"] += 1
            counts[f"filtered_{ticker}"] += 1
            records.append(
                _record_signal(
                    signal,
                    action="filtered",
                    reason="daily_official_space_slot_already_used",
                )
            )

        return original_size_signals(kept, portfolio_value, risk_pct=risk_pct)

    portfolio_engine.size_signals = size_one_slot_official_space
    try:
        yield {"counts": counts, "records": records}
    finally:
        portfolio_engine.size_signals = original_size_signals


def _routing_summary(scope: dict[str, Any]) -> dict[str, Any]:
    records = list(scope["records"])
    by_window: dict[str, dict[str, Any]] = {}
    for record in records:
        window = str(record.get("window") or "unknown")
        row = by_window.setdefault(
            window,
            {
                "count": 0,
                "tickers": Counter(),
                "actions": Counter(),
                "reasons": Counter(),
            },
        )
        row["count"] += 1
        row["tickers"][str(record.get("ticker") or "")] += 1
        row["actions"][str(record.get("action") or "unknown")] += 1
        row["reasons"][str(record.get("reason") or "unknown")] += 1
    return {
        "counts": dict(sorted(scope["counts"].items())),
        "records": records,
        "by_window": {
            label: {
                "count": row["count"],
                "tickers": dict(sorted(row["tickers"].items())),
                "actions": dict(sorted(row["actions"].items())),
                "reasons": dict(sorted(row["reasons"].items())),
            }
            for label, row in sorted(by_window.items())
        },
        "rule": (
            "During each portfolio sizing batch, allow only the first existing "
            "already-ranked official Space signal to size; leave all non-Space "
            "signals unchanged."
        ),
    }


def _run_stack(label: str, *, gates: dict[str, Any]) -> dict[str, Any]:
    variant = exp024._run_exp021_stack_variant(
        label,
        peer_nonleader_scalar=ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR,
        gates=gates,
    )
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "official_space_pool": list(OFFICIAL_SPACE_TICKERS),
        "accepted_source_diversity_peer_nonleader_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR
        ),
    }
    return variant


def _run_one_slot_stack(label: str, *, gates: dict[str, Any]) -> dict[str, Any]:
    with _one_slot_official_space_scope() as scope:
        variant = _run_stack(label, gates=gates)
    variant["parameters"] = {
        **variant["parameters"],
        "space_official_daily_sizing_slots": 1,
        "space_official_routing_basis": "first_already_ranked_signal_per_sizing_batch",
    }
    variant["space_one_slot_routing"] = _routing_summary(scope)
    return variant


def _gate(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = exp024.exp041.source_diversity_exp._aggregate_delta(
        after["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        label: exp024.exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in after["by_window"].items()
    }
    ev_improved = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] > 1e-9
    }
    ev_regressed = {
        label: metrics["expected_value_score"]
        for label, metrics in by_window_delta.items()
        if metrics["expected_value_score"] < -1e-9
    }
    routing_counts = after.get("space_one_slot_routing", {}).get("counts", {})
    filtered_count = int(routing_counts.get("filtered_official_space_signal", 0))
    kept_count = int(routing_counts.get("kept_official_space_signal", 0))
    passed = bool(
        filtered_count > 0
        and kept_count > 0
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
        "kept_official_space_signal_count": kept_count,
        "filtered_official_space_signal_count": filtered_count,
        "routing_counts": dict(sorted(routing_counts.items())),
        "reasons": {
            "routing_touched_signals": filtered_count > 0 and kept_count > 0,
            "aggregate_ev_delta_positive": aggregate_delta[
                "expected_value_score_sum"
            ]
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
    return {
        label: {
            key: row["metrics"].get(key)
            for key in (
                "worst_trade_pct",
                "max_consecutive_losses",
                "tail_loss_share",
            )
        }
        for label, row in variant["by_window"].items()
    }


def _experiment_record(payload: dict[str, Any]) -> dict[str, Any]:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_official_daily_sizing_slots",
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "official_space_pool": list(OFFICIAL_SPACE_TICKERS),
            "before_daily_slots": "unbounded_for_qualified_official_space_signals",
            "after_daily_slots": 1,
            "routing_basis": "first_already_ranked_signal_per_sizing_batch",
            "accepted_source_diversity_peer_nonleader_trend_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR
            ),
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec for label, spec in exp024.exp041.source_diversity_exp.WINDOWS.items()
        },
        "before_metrics": before["aggregate"],
        "after_metrics": after["aggregate"],
        "by_window_before_metrics": {
            label: item["metrics"] for label, item in before["by_window"].items()
        },
        "by_window_after_metrics": {
            label: item["metrics"] for label, item in after["by_window"].items()
        },
        "by_window_delta": gate["by_window_delta_vs_before"],
        "expected_value_score_delta": gate["aggregate_delta_vs_before"].get(
            "expected_value_score_sum"
        ),
        "total_pnl_delta": gate["aggregate_delta_vs_before"].get("total_pnl_sum"),
        "risk_distribution": {
            "before": _risk_distribution(before),
            "after": _risk_distribution(after),
        },
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Capital allocation/routing: the default-off Space sleeve may "
                "have better EV if daily official Space exposure is reserved "
                "for the top already-ranked candidate instead of allowing "
                "multiple same-batch official Space signals."
            ),
            "2_prior_similar_experiments": [
                "exp-20260515-019 rejected ARKX/UFO theme-beta admission across all windows.",
                "exp-20260515-021 accepted a defense-budget same-theme winner trend scalar.",
                "exp-20260515-024 accepted source-diversity peer-nonleader trend allocation.",
                "exp-20260515-031/035 rejected VSAT/mature-satcom admission due old_thin regression and drawdown.",
                "exp-20260515-037 rejected GSAT satellite-connectivity admission due aggregate EV loss and old_thin regression.",
                "No prior current-stack experiment found that isolates official Space one-slot daily routing.",
            ],
            "3_single_causal_variable": (
                "Only official Space daily sizing capacity changes from all "
                "qualified signals to one first-ranked official signal per "
                "sizing batch."
            ),
            "4_success_criteria": (
                "Routing must touch signals, aggregate EV/PnL must improve, at "
                "least two windows must improve, no window may regress, max "
                "drawdown drift <= 0.5 pp, survival >= 5%, and trade count >= 50."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260515_043_space_one_slot_official_routing.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: one-slot official Space routing did not improve "
            "the fixed three-window protocol without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not promote historical one-slot Space routing on these frozen "
            "windows. Next Space alpha should use a new production-visible "
            "catalyst-quality field or a broader mature cohort, not ticker breadth."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, one-slot routing must remain shared with the "
                "production observation slot and live Space slots remain zero "
                "until explicit pilot promotion."
                if promoted
                else "Experiment-only size_signals monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited, Space ticker breadth "
            "and ETF admission repeatedly failed cross-window gates, and recent "
            "single-event scalars were sample-thin. This tests allocation among "
            "already-qualified official candidates."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space one-slot official routing",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_official_daily_sizing_slots` on top of accepted "
            f"`{BEFORE_EXPERIMENT_ID}`."
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
        f"- official Space tickers: `{list(OFFICIAL_SPACE_TICKERS)}`",
        "- no new prompt field, news field, LLM field, price field, or threshold is required.",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{after['aggregate']['min_survival_rate']}`",
        "- this is Space sleeve capacity/routing, not a new entry filter.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, delta in gate["by_window_delta_vs_before"].items():
        before_metrics = before["by_window"][label]["metrics"]
        after_metrics = after["by_window"][label]["metrics"]
        lines.append(
            "| {label} | {ev_before:.6f} | {ev_after:.6f} | {ev_delta:.6f} | {pnl_delta:.2f} | {dd_delta:.6f} | {trades_before} | {trades_after} |".format(
                label=label,
                ev_before=before_metrics.get("expected_value_score", 0.0),
                ev_after=after_metrics.get("expected_value_score", 0.0),
                ev_delta=delta.get("expected_value_score", 0.0),
                pnl_delta=delta.get("total_pnl", 0.0),
                dd_delta=delta.get("max_drawdown_pct", 0.0),
                trades_before=before_metrics.get("trade_count", ""),
                trades_after=after_metrics.get("trade_count", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Routing Coverage",
            f"- kept official Space signals: `{gate['kept_official_space_signal_count']}`",
            f"- filtered official Space signals: `{gate['filtered_official_space_signal_count']}`",
            f"- routing counts: `{gate['routing_counts']}`",
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- max drawdown pct max delta: `{gate['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
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
            "Space one-slot routing "
            f"{payload['decision']} with EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    completed_at = datetime.now(timezone.utc).isoformat()
    gates = exp021._collect_gates()
    before = _run_stack("accepted_exp024_unbounded_official_space", gates=gates)
    after = _run_one_slot_stack("one_slot_official_space_routing", gates=gates)
    gate = _gate(after, before)
    field_check = exp051._open_position_field_check()
    decision = "accept" if field_check["passed"] and gate["passed"] else "reject"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "Default-off Space exposure may be over-allocated on days with "
            "multiple official Space candidates. Allowing only the top "
            "already-ranked official Space signal per sizing batch may improve "
            "replacement value and tail behavior without adding tickers or new "
            "LLM/rule fields."
        ),
        "official_space_pool": list(OFFICIAL_SPACE_TICKERS),
        "gates": gates,
        "field_check": field_check,
        "before_variant": before,
        "after_variant": after,
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "changed_variable": "space_official_daily_sizing_slots",
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
                    "kept_official_space_signals": gate[
                        "kept_official_space_signal_count"
                    ],
                    "filtered_official_space_signals": gate[
                        "filtered_official_space_signal_count"
                    ],
                    "aggregate_ev_delta": gate["aggregate_delta_vs_before"][
                        "expected_value_score_sum"
                    ],
                    "aggregate_pnl_delta": gate["aggregate_delta_vs_before"][
                        "total_pnl_sum"
                    ],
                    "max_drawdown_delta": gate["aggregate_delta_vs_before"][
                        "max_drawdown_pct_max"
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
