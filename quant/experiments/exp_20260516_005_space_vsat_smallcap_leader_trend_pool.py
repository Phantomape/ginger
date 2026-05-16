"""exp-20260516-005: Space VSAT smallcap-leader trend pool.

Tests one candidate-pool variable on top of the accepted exp-20260515-044
Space stack: admit the stricter VSAT mature-satcom extension only for
trend_long signals when the already production-visible small-cap appetite state
is `smallcap_leader`.

This avoids LLM soft-ranking, broad ticker expansion, entry/exit changes,
ranking changes, and live Space slots.
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
import exp_20260515_021_space_defense_budget_same_theme_winner_trend_risk as exp021
import exp_20260515_031_space_vsat_same_theme_satcom_trend_pool as exp031
import exp_20260515_044_space_source_diversity_peer_nonleader_near_perfect_trend_risk as exp044


LOGGER = logging.getLogger(__name__)

EXPERIMENT_ID = "exp-20260516-005"
STEM = "space_vsat_smallcap_leader_trend_pool"
BEFORE_EXPERIMENT_ID = "exp-20260515-044"
BEFORE_STEM = "space_source_diversity_peer_nonleader_near_perfect_trend_risk"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

TARGET_TICKER = "VSAT"
TARGET_STRATEGY = "trend_long"
TARGET_IWM_STATE = "smallcap_leader"
ACCEPTED_NEAR_PERFECT_SCALAR = 1.025
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005


def _safe(value: Any) -> Any:
    return exp044._safe(value)


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
    date_key = str(date_text or "")[:10]
    if not date_key:
        return None
    for label, spec in exp044.exp041.source_diversity_exp.WINDOWS.items():
        if str(spec["start"]) <= date_key <= str(spec["end"]):
            return label
    return None


def _record_extension_signal(
    signal: dict[str, Any],
    *,
    action: str,
    reason: str,
) -> dict[str, Any]:
    date_key = str(signal.get("date") or "")[:10]
    return {
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": signal.get("strategy"),
        "date": date_key,
        "window": _window_for_date(date_key),
        "action": action,
        "reason": reason,
        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
        "trade_quality_score": signal.get("trade_quality_score"),
        "confidence_score": signal.get("confidence_score"),
        "space_source_diversity_peer_nonleader_trend_bucket": signal.get(
            "space_source_diversity_peer_nonleader_trend_bucket"
        ),
        "space_source_diversity_peer_nonleader_near_perfect_trend_bucket": (
            signal.get(
                "space_source_diversity_peer_nonleader_near_perfect_trend_bucket"
            )
        ),
    }


@contextmanager
def _smallcap_leader_trend_extension_scope(added_tickers: tuple[str, ...]):
    """Keep extension ticker signals only in trend + smallcap-leader state."""
    original_size_signals = portfolio_engine.size_signals
    added = {str(ticker).upper() for ticker in added_tickers}
    counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []

    def size_smallcap_leader_trend_extension(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in added:
                kept.append(signal)
                continue

            strategy = str(signal.get("strategy") or "")
            iwm_state = str(signal.get("space_iwm_relative_state") or "")
            counts["extension_signal_seen"] += 1
            counts[f"seen_{ticker}"] += 1
            counts[f"seen_strategy_{strategy or 'unknown'}"] += 1
            counts[f"seen_iwm_state_{iwm_state or 'unknown'}"] += 1

            if strategy != TARGET_STRATEGY:
                counts["filtered_extension_signal"] += 1
                counts["filtered_extension_non_trend_signal"] += 1
                counts[f"filtered_{ticker}"] += 1
                records.append(
                    _record_extension_signal(
                        signal,
                        action="filtered",
                        reason="non_trend",
                    )
                )
                continue
            if iwm_state != TARGET_IWM_STATE:
                counts["filtered_extension_signal"] += 1
                counts["filtered_extension_not_smallcap_leader_signal"] += 1
                counts[f"filtered_{ticker}"] += 1
                records.append(
                    _record_extension_signal(
                        signal,
                        action="filtered",
                        reason="not_smallcap_leader",
                    )
                )
                continue

            counts["kept_extension_signal"] += 1
            counts[f"kept_{ticker}"] += 1
            records.append(
                _record_extension_signal(
                    signal,
                    action="kept",
                    reason="trend_smallcap_leader",
                )
            )
            kept.append(signal)

        return original_size_signals(kept, portfolio_value, risk_pct=risk_pct)

    portfolio_engine.size_signals = size_smallcap_leader_trend_extension
    try:
        yield {"counts": counts, "records": records}
    finally:
        portfolio_engine.size_signals = original_size_signals


def _extension_filter_summary(scope: dict[str, Any]) -> dict[str, Any]:
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
                "iwm_states": Counter(),
                "strategies": Counter(),
            },
        )
        row["count"] += 1
        row["tickers"][str(record.get("ticker") or "")] += 1
        row["actions"][str(record.get("action") or "unknown")] += 1
        row["reasons"][str(record.get("reason") or "unknown")] += 1
        row["iwm_states"][str(record.get("space_iwm_relative_state") or "unknown")] += 1
        row["strategies"][str(record.get("strategy") or "unknown")] += 1

    return {
        "counts": dict(sorted(scope["counts"].items())),
        "records": records,
        "by_window": {
            label: {
                "count": row["count"],
                "tickers": dict(sorted(row["tickers"].items())),
                "actions": dict(sorted(row["actions"].items())),
                "reasons": dict(sorted(row["reasons"].items())),
                "iwm_states": dict(sorted(row["iwm_states"].items())),
                "strategies": dict(sorted(row["strategies"].items())),
            }
            for label, row in sorted(by_window.items())
        },
        "rule": (
            "Added VSAT signals are allowed only when strategy=trend_long and "
            "space_iwm_relative_state=smallcap_leader."
        ),
    }


def _collect_gates_with_pool(tickers: tuple[str, ...]) -> dict[str, Any]:
    with exp013._official_space_pool(tickers):
        gates = exp021._collect_gates()
    gates["official_space_pool"] = list(tickers)
    gates["satcom_fast_5d_same_theme_gate"] = exp031._satcom_fast_5d_same_theme_gate()
    return gates


def _run_stack_with_pool(
    label: str,
    *,
    tickers: tuple[str, ...],
    gates: dict[str, Any],
    added_tickers: tuple[str, ...] = (),
) -> dict[str, Any]:
    filter_summary: dict[str, Any] | None = None
    with exp013._official_space_pool(tickers):
        if added_tickers:
            with _smallcap_leader_trend_extension_scope(added_tickers) as scope:
                variant = exp044._run_current_stack_variant(
                    label,
                    near_perfect_scalar=ACCEPTED_NEAR_PERFECT_SCALAR,
                    gates=gates,
                )
            filter_summary = _extension_filter_summary(scope)
        else:
            variant = exp044._run_current_stack_variant(
                label,
                near_perfect_scalar=ACCEPTED_NEAR_PERFECT_SCALAR,
                gates=gates,
            )

    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "official_space_pool": list(tickers),
        "base_official_space_pool": list(exp044.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS),
        "vsat_smallcap_leader_added_tickers": list(added_tickers),
        "vsat_smallcap_leader_allowed_strategy": TARGET_STRATEGY
        if added_tickers
        else None,
        "vsat_smallcap_leader_required_iwm_state": TARGET_IWM_STATE
        if added_tickers
        else None,
        "accepted_source_diversity_peer_nonleader_near_perfect_trend_scalar": (
            ACCEPTED_NEAR_PERFECT_SCALAR
        ),
    }
    if filter_summary is not None:
        variant["vsat_smallcap_leader_extension_filter"] = filter_summary
    return variant


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return exp044.exp041.source_diversity_exp._aggregate_delta(
        after["aggregate"],
        before["aggregate"],
    )


def _by_window_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        label: exp044.exp041.source_diversity_exp._delta(
            row["metrics"],
            before["by_window"][label]["metrics"],
        )
        for label, row in after["by_window"].items()
    }


def _space_trades_by_extension(
    variant: dict[str, Any],
    added_tickers: tuple[str, ...],
) -> dict[str, Any]:
    targets = {str(ticker).upper() for ticker in added_tickers}
    by_window: dict[str, Any] = {}
    for label, row in variant["by_window"].items():
        attribution = row.get("official_space_trade_attribution") or row.get(
            "space_trade_attribution"
        ) or {}
        trades = [
            trade
            for trade in attribution.get("trades") or []
            if str(trade.get("ticker") or "").upper() in targets
        ]
        by_window[label] = {
            "trade_count": len(trades),
            "total_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
            "wins": sum(1 for trade in trades if float(trade.get("pnl") or 0.0) > 0.0),
            "losses": sum(1 for trade in trades if float(trade.get("pnl") or 0.0) < 0.0),
            "trades": trades,
        }
    return by_window


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
    counts = (
        (after.get("vsat_smallcap_leader_extension_filter") or {}).get("counts") or {}
    )
    kept_extension_signal_count = int(counts.get("kept_extension_signal", 0))
    passed = bool(
        kept_extension_signal_count > 0
        and extension_trade_count > 0
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
        "extension_filter_counts": dict(sorted(counts.items())),
        "kept_extension_signal_count": kept_extension_signal_count,
        "filtered_not_smallcap_leader_signal_count": int(
            counts.get("filtered_extension_not_smallcap_leader_signal", 0)
        ),
        "filtered_non_trend_signal_count": int(
            counts.get("filtered_extension_non_trend_signal", 0)
        ),
        "reasons": {
            "kept_extension_signals_present": kept_extension_signal_count > 0,
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
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    return {
        "experiment_id": EXPERIMENT_ID,
        "date": payload["completed_at"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": "space_vsat_smallcap_leader_trend_pool_membership",
        "parameters": {
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "base_official_space_pool": payload["base_official_space_pool"],
            "extended_official_space_pool": payload["extended_official_space_pool"],
            "added_tickers": payload["added_tickers"],
            "candidate_universe": list(exp013.SATCOM_EXTENSION_CANDIDATES),
            "allowed_strategy_for_added_tickers": TARGET_STRATEGY,
            "required_iwm_state_for_added_tickers": TARGET_IWM_STATE,
            "forward_gate": payload["satcom_fast_5d_same_theme_gate"],
            "accepted_near_perfect_scalar": ACCEPTED_NEAR_PERFECT_SCALAR,
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in exp044.exp041.source_diversity_exp.WINDOWS.items()
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
        "extension_filter": after.get("vsat_smallcap_leader_extension_filter"),
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Candidate-pool alpha: VSAT's mature satcom profile may add "
                "Space trend continuation value only when small-cap appetite is "
                "confirmed by space_iwm_relative_state=smallcap_leader."
            ),
            "2_prior_similar_experiments": [
                "exp-20260515-029 rejected current-stack IRDM/VSAT trend-only admission because old_thin regressed and drawdown worsened.",
                "exp-20260515-031 rejected stricter VSAT-only trend admission because old_thin still regressed and late drawdown worsened.",
                "exp-20260515-035 rejected VSAT trend fallback admission; this run changes the discriminator to the production-visible smallcap_leader state.",
                "exp-20260516-001 rejected nearby current-stack Space setup-quality scalar work, and LLM soft-ranking remains data-limited.",
            ],
            "3_single_causal_variable": (
                "Only VSAT candidate-pool membership changes, and only under "
                "trend_long plus smallcap_leader. Entries, exits, ranking, "
                "stops, LLM/news, risk scalars, and live slots stay fixed."
            ),
            "4_success_criteria": (
                "Kept VSAT extension signals and trades present, aggregate EV/PnL "
                "positive, at least two EV-improved windows, no EV-regressed "
                "window, max drawdown drift <= 0.5 pp, survival >= 5%, and "
                "trade count >= 50."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260516_005_space_vsat_smallcap_leader_trend_pool.py"
            ),
        },
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: VSAT smallcap-leader trend admission did not improve "
            "the fixed three-window protocol without regression and drawdown damage."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry VSAT or mature-satcom admission on these frozen windows "
            "without additional closed forward rows or a genuinely new "
            "production-visible catalyst-quality discriminator."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": promoted,
            "run_adapter_changed": promoted,
            "replay_only": not promoted,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, VSAT membership must be expressed through shared "
                "space_catalyst_sleeve.py policy and observe-only reports; live "
                "Space slots remain zero."
                if promoted
                else "Experiment-only official-pool monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking lacks dense downstream attribution, recent Space "
            "source/TQS/benchmark scalar branches are sample-limited, and broad "
            "satcom admission added noise. This run tests one production-visible "
            "candidate-pool discriminator instead of adding generic tickers."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    promoted = payload["decision"] == "accept"
    lines = [
        f"# {EXPERIMENT_ID} Space VSAT smallcap-leader trend pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_vsat_smallcap_leader_trend_pool_membership` on top of "
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
        f"- 5d+10d same-theme satcom gate passed: `{payload['satcom_fast_5d_same_theme_gate']['passed']}`",
        f"- added tickers: `{payload['added_tickers']}`",
        f"- required state: `{TARGET_IWM_STATE}`",
        f"- kept extension signals: `{gate['kept_extension_signal_count']}`",
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
            f"- extension filter counts: `{gate['extension_filter_counts']}`",
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
            "VSAT smallcap-leader trend pool "
            f"{payload['decision']} with EV delta "
            f"{gate['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    LOGGER.info("Running %s", EXPERIMENT_ID)
    completed_at = datetime.now(timezone.utc).isoformat()
    base_pool = tuple(exp044.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)
    satcom_gate = exp031._satcom_fast_5d_same_theme_gate()
    added = tuple(
        ticker
        for ticker in satcom_gate["target_tickers"]
        if ticker == TARGET_TICKER and ticker not in base_pool
    )
    extended_pool = base_pool + tuple(ticker for ticker in added if ticker not in base_pool)

    base_gates = _collect_gates_with_pool(base_pool)
    extended_gates = _collect_gates_with_pool(extended_pool)
    before = _run_stack_with_pool(
        "accepted_exp044_base_pool",
        tickers=base_pool,
        gates=base_gates,
    )
    after = _run_stack_with_pool(
        "current_stack_vsat_smallcap_leader_trend_pool",
        tickers=extended_pool,
        gates=extended_gates,
        added_tickers=added,
    )
    gate = _gate(after, before, added_tickers=added)
    field_check = exp021.exp051._open_position_field_check()
    decision = (
        "accept"
        if field_check["passed"]
        and satcom_gate["passed"]
        and added
        and gate["passed"]
        else "reject"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "VSAT's mature satcom profile may be useful only in a favorable "
            "small-cap appetite regime: admit VSAT into the official Space pool "
            "only for trend_long signals where space_iwm_relative_state is "
            "smallcap_leader."
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
    }
    payload["experiment_log_record"] = _experiment_record(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TICKET_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = _artifact_markdown(payload)
    payload["artifact_markdown"] = artifact
    _write_json(DATA_DIR / f"{STEM}.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["experiment_log_record"])
    _write_json(TICKET_DIR / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        artifact,
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(EXPERIMENT_LOG, payload["experiment_log_record"])


def main() -> None:
    payload = run()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "added_tickers": payload["added_tickers"],
                    "kept_extension_signal_count": payload["gate_results"][
                        "kept_extension_signal_count"
                    ],
                    "extension_trade_count": payload["gate_results"][
                        "extension_trade_count"
                    ],
                    "aggregate_ev_delta": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["expected_value_score_sum"],
                    "aggregate_pnl_delta": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["total_pnl_sum"],
                    "max_drawdown_delta": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["max_drawdown_pct_max"],
                    "improved_windows": payload["gate_results"]["improved_windows"],
                    "regressed_windows": payload["gate_results"]["regressed_windows"],
                    "gate4_passed": payload["gate_results"]["passed"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
