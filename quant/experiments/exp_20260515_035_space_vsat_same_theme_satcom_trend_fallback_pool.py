"""
exp-20260515-035: Space VSAT same-theme satcom trend fallback pool.

Tests one candidate-pool variable on top of the accepted exp-20260515-024
Space stack: add the stricter VSAT 5d+10d same-theme mature-satcom extension
only as a trend_long fallback when no base official Space signal is present on
the same signal date.

This is the non-displacing design requested by the rejected exp-20260515-031
result. It does not change exits, ranking, stops, LLM authority, or live Space
slots.
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
import exp_20260515_013_space_fast_5d_satcom_candidate_pool as exp013
import exp_20260515_015_space_fast_5d_satcom_trend_only_pool as exp015
import exp_20260515_021_space_defense_budget_same_theme_winner_trend_risk as exp021
import exp_20260515_024_space_source_diversity_peer_nonleader_trend_risk as exp024
import exp_20260515_029_space_current_stack_fast_5d_satcom_trend_pool as exp029
import exp_20260515_031_space_vsat_same_theme_satcom_trend_pool as exp031


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260515-035"
STEM = "space_vsat_same_theme_satcom_trend_fallback_pool"
BEFORE_EXPERIMENT_ID = "exp-20260515-024"
BEFORE_STEM = "space_source_diversity_peer_nonleader_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_STRATEGY = "trend_long"
ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR = 1.025


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
    return exp015._window_for_date(date_text)


@contextmanager
def _trend_fallback_extension_scope(
    added_tickers: tuple[str, ...],
    base_tickers: tuple[str, ...],
):
    """Keep extension signals only if they are trend fallback on base-empty dates."""
    original_size_signals = portfolio_engine.size_signals
    added = {str(ticker).upper() for ticker in added_tickers}
    base = {str(ticker).upper() for ticker in base_tickers}
    counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []

    def size_trend_fallback_extension(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        signals_by_date: dict[str, list[dict[str, Any]]] = {}
        for signal in signals:
            date_key = str(signal.get("date") or "")[:10]
            signals_by_date.setdefault(date_key, []).append(signal)

        dates_with_base_space_signal = {
            date_key
            for date_key, rows in signals_by_date.items()
            if any(str(row.get("ticker") or "").upper() in base for row in rows)
        }

        kept: list[dict[str, Any]] = []
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in added:
                kept.append(signal)
                continue

            strategy = str(signal.get("strategy") or "")
            date_key = str(signal.get("date") or "")[:10]
            if strategy != TARGET_STRATEGY:
                counts["filtered_extension_signal"] += 1
                counts["filtered_extension_non_trend_signal"] += 1
                counts[f"filtered_{ticker}"] += 1
                counts[f"filtered_{strategy or 'unknown'}"] += 1
                records.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "date": date_key,
                        "window": _window_for_date(date_key),
                        "action": "filtered",
                        "reason": "non_trend",
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_iwm_relative_state": signal.get(
                            "space_iwm_relative_state"
                        ),
                    }
                )
                continue
            if date_key in dates_with_base_space_signal:
                counts["filtered_extension_signal"] += 1
                counts["filtered_extension_official_same_day_signal"] += 1
                counts[f"filtered_{ticker}"] += 1
                records.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "date": date_key,
                        "window": _window_for_date(date_key),
                        "action": "filtered",
                        "reason": "official_same_day",
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_iwm_relative_state": signal.get(
                            "space_iwm_relative_state"
                        ),
                    }
                )
                continue
            counts["kept_extension_signal"] += 1
            counts[f"kept_{ticker}"] += 1
            kept.append(signal)

        return original_size_signals(kept, portfolio_value, risk_pct=risk_pct)

    portfolio_engine.size_signals = size_trend_fallback_extension
    try:
        yield {"counts": counts, "records": records}
    finally:
        portfolio_engine.size_signals = original_size_signals


def _fallback_filter_summary(scope: dict[str, Any]) -> dict[str, Any]:
    records = list(scope["records"])
    by_window: dict[str, dict[str, Any]] = {}
    for record in records:
        window = str(record.get("window") or "unknown")
        row = by_window.setdefault(
            window,
            {"count": 0, "tickers": Counter(), "actions": Counter(), "reasons": Counter()},
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
            "Added satcom tickers are allowed only for trend_long signals on "
            "dates with no base official Space signal in the same sizing batch."
        ),
    }


def _run_stack_with_fallback_pool(
    label: str,
    *,
    tickers: tuple[str, ...],
    gates: dict[str, Any],
    added_tickers: tuple[str, ...] = (),
    base_tickers: tuple[str, ...] = (),
) -> dict[str, Any]:
    fallback_summary: dict[str, Any] | None = None
    with exp013._official_space_pool(tickers):
        if added_tickers:
            with _trend_fallback_extension_scope(added_tickers, base_tickers) as scope:
                variant = exp024._run_exp021_stack_variant(
                    label,
                    peer_nonleader_scalar=(
                        ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR
                    ),
                    gates=gates,
                )
            fallback_summary = _fallback_filter_summary(scope)
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
        "base_official_space_pool": list(base_tickers),
        "satcom_fallback_added_tickers": list(added_tickers),
        "satcom_fallback_allowed_strategy": TARGET_STRATEGY
        if added_tickers
        else None,
        "accepted_source_diversity_peer_nonleader_trend_scalar": (
            ACCEPTED_SOURCE_DIVERSITY_PEER_NONLEADER_SCALAR
        ),
    }
    if fallback_summary is not None:
        variant["satcom_trend_fallback_extension_filter"] = fallback_summary
    return variant


def _gate(
    after: dict[str, Any],
    before: dict[str, Any],
    *,
    added_tickers: tuple[str, ...],
) -> dict[str, Any]:
    gate = exp029._gate(after, before, added_tickers=added_tickers)
    counts = (
        (after.get("satcom_trend_fallback_extension_filter") or {}).get("counts") or {}
    )
    gate["fallback_filter_counts"] = counts
    gate["fallback_kept_extension_signal_count"] = int(
        counts.get("kept_extension_signal", 0)
    )
    gate["fallback_filtered_official_same_day_signal_count"] = int(
        counts.get("filtered_extension_official_same_day_signal", 0)
    )
    gate["non_trend_filtered_extension_signal_count"] = int(
        counts.get("filtered_extension_non_trend_signal", 0)
    )
    gate["reasons"]["fallback_signals_present"] = (
        gate["fallback_kept_extension_signal_count"] > 0
    )
    return gate


def _risk_distribution(variant: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return exp031._risk_distribution(variant)


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
        "changed_variable": (
            "space_fast_5d_10d_same_theme_satcom_trend_fallback_pool_membership"
        ),
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "base_official_space_pool": payload["base_official_space_pool"],
            "extended_official_space_pool": payload["extended_official_space_pool"],
            "added_tickers": payload["added_tickers"],
            "candidate_universe": list(exp013.SATCOM_EXTENSION_CANDIDATES),
            "allowed_strategy_for_added_tickers": TARGET_STRATEGY,
            "fallback_rule": (
                "allow added ticker only when no base official Space signal is "
                "present on the same signal date"
            ),
            "forward_gate": payload["satcom_fast_5d_same_theme_gate"],
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
        "fallback_filter": after.get("satcom_trend_fallback_extension_filter"),
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Candidate-pool alpha: the stricter VSAT mature-satcom profile "
                "may add trend continuation value only as fallback exposure when "
                "base official Space candidates are absent."
            ),
            "2_prior_similar_experiments": [
                "exp-20260515-029 rejected current-stack IRDM/VSAT trend-only admission because old_thin regressed and drawdown worsened.",
                "exp-20260515-031 rejected stricter VSAT-only trend admission because old_thin still regressed and late drawdown worsened.",
                "This run changes only the admission design to fallback-only on same-day base official Space emptiness.",
            ],
            "3_single_causal_variable": (
                "Only the satcom extension membership rule changes from no "
                "extension to VSAT trend fallback on base-empty Space signal dates."
            ),
            "4_success_criteria": (
                "Extension trades present, aggregate EV/PnL positive, at least "
                "two EV-improved windows, no EV-regressed windows, max drawdown "
                "drift <= 0.5 pp, survival >= 5%, and trade count >= 50."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260515_035_space_vsat_same_theme_satcom_trend_fallback_pool.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: fallback-only VSAT admission still did not improve "
            "the fixed three-window protocol without regression."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry VSAT-only, IRDM/VSAT, or mature-satcom fallback "
            "admission on these frozen windows without additional closed forward "
            "rows or a new production-visible catalyst-quality field."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, fallback membership must be expressed through "
                "shared space_catalyst_sleeve.py and observe-only reports; live "
                "Space slots remain zero."
                if promoted
                else "Experiment-only official-pool monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking lacks attribution depth, ARKX/UFO theme-beta "
            "admission failed all windows, and one-ticker Space scalars are "
            "sample-limited. This tests the remaining non-displacing candidate "
            "pool design rather than adding noisy tickers."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space VSAT same-theme satcom trend fallback pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_fast_5d_10d_same_theme_satcom_trend_fallback_pool_membership` "
            f"on top of accepted `{BEFORE_EXPERIMENT_ID}`."
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
        f"- 5d+10d same-theme satcom gate passed: `{payload['satcom_fast_5d_same_theme_gate']['passed']}`",
        f"- added tickers: `{payload['added_tickers']}`",
        f"- fallback kept extension signals: `{gate['fallback_kept_extension_signal_count']}`",
        f"- official-same-day extension signals filtered: `{gate['fallback_filtered_official_same_day_signal_count']}`",
        "",
        "## Gate 3 Survival Audit",
        f"- min survival before: `{before['aggregate']['min_survival_rate']}`",
        f"- min survival after: `{after['aggregate']['min_survival_rate']}`",
        "- this is a candidate-scope membership test, not a new core filter.",
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
            f"- max drawdown pct max delta: `{gate['aggregate_delta_vs_before']['max_drawdown_pct_max']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
            f"- fallback filter counts: `{gate['fallback_filter_counts']}`",
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
            "VSAT fallback satcom trend pool "
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
    satcom_gate = exp031._satcom_fast_5d_same_theme_gate()
    added = tuple(
        ticker for ticker in satcom_gate["target_tickers"] if ticker not in base_pool
    )
    extended_pool = tuple(sorted(set(base_pool) | set(added)))

    base_gates = exp029._collect_gates_with_pool(base_pool)
    extended_gates = exp029._collect_gates_with_pool(extended_pool)
    before = _run_stack_with_fallback_pool(
        "accepted_exp024_base_pool",
        tickers=base_pool,
        gates=base_gates,
    )
    after = _run_stack_with_fallback_pool(
        "current_stack_vsat_same_theme_satcom_trend_fallback_pool",
        tickers=extended_pool,
        gates=extended_gates,
        added_tickers=added,
        base_tickers=base_pool,
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
            "VSAT's mature satcom profile may be useful only as a non-displacing "
            "trend fallback: admit VSAT only when it passes the 5d+10d same-theme "
            "gate and no base official Space signal exists on that signal date."
        ),
        "base_official_space_pool": list(base_pool),
        "extended_official_space_pool": list(extended_pool),
        "added_tickers": list(added),
        "base_gates": base_gates,
        "extended_gates": extended_gates,
        "satcom_fast_5d_same_theme_gate": satcom_gate,
        "field_check": field_check,
        "before_variant": before,
        "after_variant": after,
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "changed_variable": (
            "space_fast_5d_10d_same_theme_satcom_trend_fallback_pool_membership"
        ),
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
                    "fallback_kept_signals": gate[
                        "fallback_kept_extension_signal_count"
                    ],
                    "fallback_filtered_official_same_day_signals": gate[
                        "fallback_filtered_official_same_day_signal_count"
                    ],
                    "extension_trades": gate["extension_trade_count"],
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
