"""exp-20260510-011: MRVL AI connectivity candidate replay.

Alpha search. Test whether adding only MRVL, a liquid AI connectivity/custom
silicon candidate already present in the historical fresh OHLCV set, improves
the accepted stack more cleanly than prior broad watchlist expansion. This
does not alter production universe, ranking, sizing, exits, LLM, news, or event
sleeves.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-011"
SOURCE_EXPERIMENT_ID = "exp-20260505-009"
SUB_BASKET = ["MRVL"]

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_late_strong_fresh_ohlcv.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_mid_weak_fresh_ohlcv.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_old_thin_fresh_ohlcv.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "mrvl_ai_connectivity_candidate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_mrvl_ai_connectivity_candidate.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        "worst_3_trade_cluster_pct": _round(result.get("worst_3_trade_cluster_pct"), 4),
        "alpha_per_heat": _round(result.get("alpha_per_heat"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {
                "trade_count",
                "signals_generated",
                "signals_survived",
                "max_consecutive_losses",
            }:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _run_engine(universe: list[str], window: dict[str, str]) -> dict[str, Any]:
    snapshot = REPO_ROOT / window["snapshot"]
    if not snapshot.exists():
        raise FileNotFoundError(
            f"Required snapshot missing: {snapshot}. Run {SOURCE_EXPERIMENT_ID} first."
        )
    result = BacktestEngine(
        universe=universe,
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(snapshot),
    ).run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _candidate_trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_set = set(SUB_BASKET)
    rows = [
        trade for trade in trades
        if str(trade.get("ticker") or "").upper() in candidate_set
    ]
    return {
        "trade_count": len(rows),
        "wins": sum(1 for trade in rows if float(trade.get("pnl") or 0.0) > 0),
        "losses": sum(1 for trade in rows if float(trade.get("pnl") or 0.0) <= 0),
        "total_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in rows), 2),
        "trades": [
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "pnl": _round(trade.get("pnl"), 2),
                "return_pct": _round(trade.get("return_pct"), 4),
                "exit_reason": trade.get("exit_reason"),
            }
            for trade in rows
        ],
    }


def _aggregate(rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(float(row["before"]["expected_value_score"] or 0.0) for row in rows.values())
    ev_delta = sum(float(row["delta"]["expected_value_score"] or 0.0) for row in rows.values())
    pnl_before = sum(float(row["before"]["total_pnl"] or 0.0) for row in rows.values())
    pnl_delta = sum(float(row["delta"]["total_pnl"] or 0.0) for row in rows.values())
    return {
        "expected_value_score_before_sum": _round(ev_before, 6),
        "expected_value_score_delta_sum": _round(ev_delta, 6),
        "expected_value_score_delta_pct": _round(ev_delta / ev_before if ev_before else 0.0, 6),
        "total_pnl_before_sum": _round(pnl_before, 2),
        "total_pnl_delta_sum": _round(pnl_delta, 2),
        "total_pnl_delta_pct": _round(pnl_delta / pnl_before if pnl_before else 0.0, 6),
        "ev_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) > 0
        ),
        "ev_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("expected_value_score", 0) < 0
        ),
        "pnl_windows_improved": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) > 0
        ),
        "pnl_windows_regressed": sum(
            1 for row in rows.values() if row["delta"].get("total_pnl", 0) < 0
        ),
        "max_drawdown_delta_max": _round(
            max(row["delta"].get("max_drawdown_pct", 0.0) for row in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(row["delta"].get("trade_count", 0) for row in rows.values()),
        "survival_rate_delta_min": _round(
            min(row["delta"].get("survival_rate", 0.0) for row in rows.values()), 6
        ),
        "candidate_trade_count_sum": sum(
            row["candidate_trade_stats"]["trade_count"] for row in rows.values()
        ),
        "candidate_pnl_sum": _round(
            sum(row["candidate_trade_stats"]["total_pnl"] or 0.0 for row in rows.values()), 2
        ),
    }


def _decision(aggregate: dict[str, Any]) -> tuple[str, str]:
    ev_pct = aggregate["expected_value_score_delta_pct"] or 0.0
    pnl_pct = aggregate["total_pnl_delta_pct"] or 0.0
    if (
        ev_pct > 0.10
        and aggregate["ev_windows_regressed"] == 0
        and aggregate["pnl_windows_regressed"] == 0
        and aggregate["candidate_trade_count_sum"] >= 3
        and aggregate["max_drawdown_delta_max"] <= 1.0
    ):
        return (
            "promising_replay_only_do_not_promote",
            "Static candidate-pool result is positive but needs PIT/live pilot validation.",
        )
    if (
        aggregate["ev_windows_improved"] >= 2
        and aggregate["candidate_pnl_sum"] > 0
        and (ev_pct > 0 or pnl_pct > 0.03)
    ):
        return (
            "watchlist_replay_only",
            "Some positive evidence, but not enough for production promotion.",
        )
    return (
        "rejected",
        "MRVL-only candidate expansion did not produce robust three-window EV improvement.",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != payload["experiment_id"]:
                kept.append(line)
    kept.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} MRVL AI Connectivity Candidate",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Protocol",
        "",
        payload["backtest_protocol"],
        "",
        "## Three-window deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | Survival delta | Trades delta | MRVL trades | MRVL PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["delta_metrics"]["windows"].items():
        delta = row["delta"]
        stats = row["candidate_trade_stats"]
        lines.append(
            "| {name} | {ev} | {pnl} | {sharpe} | {dd} | {survival} | {trades} | {candidate_trades} | {candidate_pnl} |".format(
                name=name,
                ev=delta.get("expected_value_score"),
                pnl=delta.get("total_pnl"),
                sharpe=delta.get("sharpe_daily"),
                dd=delta.get("max_drawdown_pct"),
                survival=delta.get("survival_rate"),
                trades=delta.get("trade_count"),
                candidate_trades=stats["trade_count"],
                candidate_pnl=stats["total_pnl"],
            )
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        f"- EV before sum: `{aggregate['expected_value_score_before_sum']}`",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']}` ({aggregate['expected_value_score_delta_pct']})",
        f"- PnL before sum: `${aggregate['total_pnl_before_sum']}`",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']}` ({aggregate['total_pnl_delta_pct']})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}/{aggregate['ev_windows_regressed']}`",
        f"- PnL windows improved/regressed: `{aggregate['pnl_windows_improved']}/{aggregate['pnl_windows_regressed']}`",
        f"- MRVL trades/PnL: `{aggregate['candidate_trade_count_sum']}` / `${aggregate['candidate_pnl_sum']}`",
        "",
        "## Production impact",
        "",
        "```text",
        "production_impact:",
        f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
        f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
        f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
        f"  replay_only: {payload['production_impact']['replay_only']}",
        f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
        "```",
        "",
        "## Decision rationale",
        "",
        payload["rejection_reason"],
        "",
        "Next evidence needed: " + payload["next_evidence_needed"],
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    base_universe = sorted(get_universe())
    overlap = sorted(set(base_universe).intersection(SUB_BASKET))
    if overlap:
        raise RuntimeError(f"Candidate already in base universe: {overlap}")
    expanded_universe = sorted(set(base_universe).union(SUB_BASKET))

    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for name, window in WINDOWS.items():
        before_result = _run_engine(base_universe, window)
        after_result = _run_engine(expanded_universe, window)
        before = _metrics(before_result)
        after = _metrics(after_result)
        rows[name] = {
            "window": {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
                "state_note": window["state_note"],
            },
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "candidate_trade_stats": _candidate_trade_stats(after_result.get("trades") or []),
        }

    aggregate = _aggregate(rows)
    decision, rejection_reason = _decision(aggregate)
    run_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_at": run_at,
        "hypothesis": (
            "Adding only MRVL to the candidate universe may capture AI "
            "connectivity/custom silicon momentum with less noise than the "
            "rejected broad historical watchlist expansion."
        ),
        "change_type": "alpha_search",
        "changed_variable": "candidate_universe_adds_mrvl_only",
        "parameters": {
            "subbasket_tickers": SUB_BASKET,
            "source_experiment_id": SOURCE_EXPERIMENT_ID,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "regime_aware_exit": True,
            "replay_llm": False,
            "replay_news": False,
        },
        "backtest_protocol": (
            "Three fixed windows from docs/backtesting.md. Canonical snapshots "
            "do not contain MRVL, so this replay uses the existing "
            "exp-20260505-009 fresh OHLCV snapshots over the same dates."
        ),
        "date_range": {
            name: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for name, window in WINDOWS.items()
        },
        "before_metrics": {
            "aggregate": {
                "expected_value_score_sum": aggregate["expected_value_score_before_sum"],
                "total_pnl_sum": aggregate["total_pnl_before_sum"],
            },
            "windows": {name: row["before"] for name, row in rows.items()},
        },
        "after_metrics": {
            "aggregate": {
                "expected_value_score_sum": _round(
                    aggregate["expected_value_score_before_sum"]
                    + aggregate["expected_value_score_delta_sum"],
                    6,
                ),
                "total_pnl_sum": _round(
                    aggregate["total_pnl_before_sum"] + aggregate["total_pnl_delta_sum"],
                    2,
                ),
            },
            "windows": {name: row["after"] for name, row in rows.items()},
        },
        "delta_metrics": {
            "aggregate": aggregate,
            "windows": rows,
        },
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If kept under watch, validate with point-in-time candidate selection "
            "or a live pilot sleeve before any production universe change."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "why_not_other_changes": (
            "RS20, ETF overlay, add-on, and LLM soft-ranking retunes are already "
            "same-sample saturated or awaiting forward data. This isolates one "
            "candidate-pool variable instead of adding noisy tickers."
        ),
        "known_risks": [
            "Uses static historical membership rather than a point-in-time production selector.",
            "Uses fresh OHLCV snapshots from exp-20260505-009 because canonical snapshots lack MRVL.",
            "Single-name evidence can be fragile even across three fixed windows.",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "title": "MRVL AI connectivity candidate replay",
        "status": decision,
        "created_at": run_at,
        "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        "next_evidence_needed": payload["next_evidence_needed"],
    })
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "aggregate": aggregate,
        "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
