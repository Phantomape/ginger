"""exp-20260515-015: Space fast-5d satcom trend-only candidate pool.

Tests one candidate-pool discriminator on top of the accepted exp-20260514-053
Space stack: forward-qualified satcom extension tickers are admitted only for
`trend_long` continuation signals, not broad breakout participation.

This is the tighter ex-ante strategy-scope discriminator requested by the
rejected exp-20260515-013 satcom extension. It avoids LLM soft-ranking, broad
ticker expansion, lifecycle changes, live Space slot changes, and nearby scalar
retunes.
"""

from __future__ import annotations

import json
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
import exp_20260515_012_space_fast_5d_benchmark_trend_risk as exp012
import exp_20260515_013_space_fast_5d_satcom_candidate_pool as exp013


EXPERIMENT_ID = "exp-20260515-015"
STEM = "space_fast_5d_satcom_trend_only_pool"
BEFORE_EXPERIMENT_ID = "exp-20260514-053"
BEFORE_STEM = "space_benchmark_breadth_iwm_leader_trend_risk"
TARGET_STRATEGY = "trend_long"

DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
DOCS_DIR = ROOT / "docs" / "experiments"
LOG_DIR = DOCS_DIR / "logs"
TICKET_DIR = DOCS_DIR / "tickets"
ARTIFACT_DIR = DOCS_DIR / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005


def _safe(value: Any) -> Any:
    return exp013._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    exp013._write_json(path, payload)


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
    lines.append(json.dumps(_safe(payload), ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _window_for_date(date_text: str) -> str | None:
    date_key = str(date_text or "")[:10]
    if not date_key:
        return None
    for label, spec in exp012.exp041.source_diversity_exp.WINDOWS.items():
        if spec["start"] <= date_key <= spec["end"]:
            return label
    return None


@contextmanager
def _trend_only_extension_scope(added_tickers: tuple[str, ...]):
    """Filter only extension-ticker non-trend signals before sizing."""
    original_size_signals = portfolio_engine.size_signals
    added = {str(ticker).upper() for ticker in added_tickers}
    records: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def size_trend_only_extension(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        kept: list[dict[str, Any]] = []
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "")
            if ticker in added and strategy != TARGET_STRATEGY:
                counts["filtered_extension_signal"] += 1
                counts[f"filtered_{ticker}"] += 1
                counts[f"filtered_{strategy or 'unknown'}"] += 1
                records.append(
                    {
                        "ticker": ticker,
                        "strategy": strategy,
                        "date": str(signal.get("date") or ""),
                        "window": _window_for_date(str(signal.get("date") or "")),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_iwm_relative_state": signal.get(
                            "space_iwm_relative_state"
                        ),
                    }
                )
                continue
            kept.append(signal)
        return original_size_signals(kept, portfolio_value, risk_pct=risk_pct)

    portfolio_engine.size_signals = size_trend_only_extension
    try:
        yield {"counts": counts, "records": records}
    finally:
        portfolio_engine.size_signals = original_size_signals


def _run_trend_only_pool(
    label: str,
    tickers: tuple[str, ...],
    gates: dict[str, Any],
    added_tickers: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _trend_only_extension_scope(added_tickers) as scope:
        variant = exp013._run_with_pool(label, tickers, gates)
    records = list(scope["records"])
    by_window: dict[str, dict[str, Any]] = {}
    for record in records:
        window = record.get("window") or "unknown"
        row = by_window.setdefault(window, {"count": 0, "tickers": Counter(), "strategies": Counter()})
        row["count"] += 1
        row["tickers"][record["ticker"]] += 1
        row["strategies"][record["strategy"] or "unknown"] += 1
    summary = {
        "counts": dict(sorted(scope["counts"].items())),
        "records": records,
        "by_window": {
            label: {
                "count": row["count"],
                "tickers": dict(sorted(row["tickers"].items())),
                "strategies": dict(sorted(row["strategies"].items())),
            }
            for label, row in sorted(by_window.items())
        },
    }
    variant["trend_only_extension_filter"] = summary
    return variant, summary


def _aggregate_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return exp012.exp041.source_diversity_exp._aggregate_delta(
        after["aggregate"],
        before["aggregate"],
    )


def _by_window_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        label: exp012.exp041.source_diversity_exp._delta(
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
    extension_trade_count = sum(
        row["trade_count"]
        for row in _space_trades_by_extension(after, added_tickers).values()
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
        "extension_trade_count": extension_trade_count,
        "reasons": {
            "extension_trades_present": extension_trade_count > 0,
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"] > 0.0,
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
            "trend_only_filter": payload["trend_only_filter"],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": (
            "docs/backtesting.md fixed 3-window Space protocol using frozen "
            "Space augmented snapshots"
        ),
        "date_range": {
            label: spec
            for label, spec in exp012.exp041.source_diversity_exp.WINDOWS.items()
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
        "extension_trade_attribution": payload["extension_trade_attribution"],
        "gate_results": gate,
        "decision": payload["decision"],
        "rejection_reason": None
        if promoted
        else (
            "Gate 4 failed: trend-only satcom extension did not improve the "
            "fixed windows without regression and drawdown damage."
        ),
        "next_evidence_needed": None
        if promoted
        else (
            "Do not retry satcom strategy-scope admission without new closed "
            "forward rows or a different production-visible catalyst-quality "
            "field."
        ),
        "production_impact": {
            "shared_policy_changed": promoted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": promoted,
            "replay_only": True,
            "parity_test_added": promoted,
            "live_slots": 0,
            "notes": (
                "If promoted, shared Space observe-only metadata should include "
                "the fast-5d satcom trend-only extension; live slots remain zero."
                if promoted
                else "Experiment-only strategy-scope monkey patch; no live policy promoted."
            ),
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains data-limited; broad satcom admission "
            "failed exp-20260515-013 because breakout participation damaged old "
            "thin and drawdown. This tests only a production-visible strategy "
            "scope discriminator on the same forward-qualified mature satcom "
            "cohort."
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    before = payload["before_variant"]
    after = payload["after_variant"]
    gate = payload["gate_results"]
    lines = [
        f"# {EXPERIMENT_ID} Space fast-5d satcom trend-only pool",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_fast_5d_satcom_trend_only_pool_membership`: add only mature "
            "fast-5d satcom tickers, and admit them only for `trend_long` "
            f"signals on top of accepted `{BEFORE_EXPERIMENT_ID}`."
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
        extension = payload["extension_trade_attribution"][label]["trade_count"]
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
            "## Trend-Only Filter Touches",
            f"- filtered non-trend extension signals: `{payload['trend_only_filter']['counts'].get('filtered_extension_signal', 0)}`",
            f"- filtered by window: `{payload['trend_only_filter']['by_window']}`",
            "",
            "## Decision",
            f"- decision: `{payload['decision']}`",
            f"- Gate 4 passed: `{gate['passed']}`",
            f"- aggregate EV delta: `{gate['aggregate_delta_vs_before']['expected_value_score_sum']}`",
            f"- aggregate PnL delta: `{gate['aggregate_delta_vs_before']['total_pnl_sum']}`",
            f"- improved windows: `{gate['improved_windows']}`",
            f"- regressed windows: `{gate['regressed_windows']}`",
            f"- extension trades: `{gate['extension_trade_count']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {str(payload['decision'] == 'accept').lower()}",
            "  backtester_adapter_changed: false",
            f"  run_adapter_changed: {str(payload['decision'] == 'accept').lower()}",
            "  replay_only: true",
            f"  parity_test_added: {str(payload['decision'] == 'accept').lower()}",
            "  live_slots: 0",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "summary": (
            "Fast-5d satcom trend-only pool "
            f"{payload['decision']} with EV delta "
            f"{payload['gate_results']['aggregate_delta_vs_before']['expected_value_score_sum']}."
        ),
        "artifact": str(ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"),
        "json": str(DATA_DIR / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc).isoformat()
    base_pool = tuple(exp012.exp041.source_diversity_exp.OFFICIAL_SPACE_TICKERS)
    satcom_gate = exp013._satcom_fast_5d_gate()
    added = tuple(
        ticker for ticker in satcom_gate["target_tickers"] if ticker not in base_pool
    )
    extended_pool = tuple(sorted(set(base_pool) | set(added)))

    base_gates = exp013._collect_gates_with_pool(base_pool)
    extended_gates = exp013._collect_gates_with_pool(extended_pool)
    before = exp013._run_with_pool("accepted_exp053_base_pool", base_pool, base_gates)
    after, trend_filter = _run_trend_only_pool(
        "fast_5d_satcom_trend_only_pool",
        extended_pool,
        extended_gates,
        added,
    )
    gate = _gate(after, before, added_tickers=added)
    field_check = exp012.exp051._open_position_field_check()
    decision = (
        "accept"
        if field_check["passed"] and satcom_gate["passed"] and gate["passed"]
        else "reject"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "hypothesis": (
            "Forward-qualified mature satcom extension tickers may add Space "
            "replacement value only as trend continuation; allowing their "
            "breakout signals imports drawdown noise."
        ),
        "base_official_space_pool": list(base_pool),
        "extended_official_space_pool": list(extended_pool),
        "added_tickers": list(added),
        "satcom_fast_5d_gate": satcom_gate,
        "field_check": field_check,
        "base_gates": base_gates,
        "extended_gates": extended_gates,
        "before_variant": before,
        "after_variant": after,
        "trend_only_filter": trend_filter,
        "extension_trade_attribution": _space_trades_by_extension(after, added),
        "gate_results": gate,
        "decision": decision,
        "protocol": "docs/backtesting.md fixed 3-window Space protocol",
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate pool: mature all-positive 5d satcom extension should "
                "be admitted only for trend_long continuation, not breakouts."
            ),
            "2_history_check": {
                "exp-20260511-026": (
                    "Rejected broad IRDM/VSAT/SATS extension without mature "
                    "forward evidence."
                ),
                "exp-20260515-013": (
                    "Rejected fast-5d satcom extension despite strong aggregate "
                    "EV because old_thin regressed and late_strong drawdown "
                    "damage exceeded the guardrail; extension losses came from "
                    "breakout_long participation."
                ),
                "exp-20260515-012": (
                    "Rejected fast-5d benchmark trend scalar due zero runtime "
                    "coverage; this run tests candidate-scope, not a scalar."
                ),
            },
            "3_single_causal_variable": (
                "space_fast_5d_satcom_trend_only_pool_membership. The accepted "
                "Space risk stack, exits, ranking, LLM/news, and live slots stay "
                "fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed Space windows; require positive "
                "aggregate EV and PnL, at least two EV-improved windows, no "
                "EV-regressed window, max drawdown drift <= 0.5 pp, survival >= "
                "5%, >=50 trades, and nonzero extension trades."
            ),
            "5_reproducibility": (
                f".venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
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
                    "filtered_non_trend_extension_signals": payload[
                        "trend_only_filter"
                    ]["counts"].get("filtered_extension_signal", 0),
                    "extension_trade_count": payload["gate_results"][
                        "extension_trade_count"
                    ],
                    "aggregate_ev_delta": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["expected_value_score_sum"],
                    "aggregate_pnl_delta": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["total_pnl_sum"],
                    "improved_windows": payload["gate_results"]["improved_windows"],
                    "regressed_windows": payload["gate_results"]["regressed_windows"],
                    "drawdown_delta_max": payload["gate_results"][
                        "aggregate_delta_vs_before"
                    ]["max_drawdown_pct_max"],
                }
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
