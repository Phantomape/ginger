"""exp-20260506-017: VNET China cloud infrastructure candidate replay.

Alpha search only. This tests a narrow candidate-pool addition after LLM/event
ranking paths were blocked by sparse forward samples. It does not alter the
production universe, ranking, sizing, exits, LLM, news, or event sleeves.
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


EXPERIMENT_ID = "exp-20260506-017"
SOURCE_EXPERIMENT_ID = "exp-20260505-009"
CANDIDATE_TICKERS = ["VNET"]

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
        "state_note": "rotation-heavy bull where strategy profits but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/experiments/exp-20260505-009/ohlcv/exp-20260505-009_old_thin_fresh_ohlcv.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "vnet_china_cloud_candidate.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_vnet_china_cloud_candidate.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


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
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    out: dict[str, Any] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived"}:
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


def _candidate_stats(trades: list[dict[str, Any]], tickers: set[str]) -> dict[str, Any]:
    rows = [
        trade for trade in trades
        if str(trade.get("ticker") or "").upper() in tickers
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
        "sharpe_daily_delta_max": _round(
            max(row["delta"].get("sharpe_daily", 0.0) for row in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(row["delta"].get("trade_count", 0) for row in rows.values()),
        "win_rate_delta_min": _round(
            min(row["delta"].get("win_rate", 0.0) for row in rows.values()), 6
        ),
        "candidate_trade_count_sum": sum(
            row["candidate_trade_stats"]["trade_count"] for row in rows.values()
        ),
        "candidate_pnl_sum": _round(
            sum(row["candidate_trade_stats"]["total_pnl"] or 0.0 for row in rows.values()), 2
        ),
    }


def _accepted(aggregate: dict[str, Any]) -> bool:
    majority_ev = aggregate["ev_windows_improved"] >= 2
    material_primary = (aggregate["expected_value_score_delta_pct"] or 0.0) > 0.10
    material_pnl = (
        (aggregate["total_pnl_delta_pct"] or 0.0) > 0.05
        and (aggregate["expected_value_score_delta_sum"] or 0.0) > 0.0
    )
    return bool(majority_ev and (material_primary or material_pnl))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(payload: dict[str, Any]) -> None:
    entry = {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["generated_at"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "hypothesis": payload["hypothesis"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "production_impact": payload["production_impact"],
    }
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} VNET China Cloud Candidate",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-window deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | VNET trades | VNET PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        delta = row["delta"]
        stats = row["candidate_trade_stats"]
        lines.append(
            f"| `{label}` | {delta['expected_value_score']:+.4f} | "
            f"{delta['total_pnl']:+.2f} | {delta['sharpe_daily']:+.2f} | "
            f"{delta['max_drawdown_pct']:+.4f} | {delta['win_rate']:+.4f} | "
            f"{delta['trade_count']:+d} | {stats['trade_count']} | "
            f"{stats['total_pnl']:+.2f} |"
        )
    lines.extend([
        "",
        "## Aggregate",
        "",
        f"- EV delta sum: `{aggregate['expected_value_score_delta_sum']:+.4f}` "
        f"({aggregate['expected_value_score_delta_pct']:+.2%})",
        f"- PnL delta sum: `${aggregate['total_pnl_delta_sum']:+,.2f}` "
        f"({aggregate['total_pnl_delta_pct']:+.2%})",
        f"- EV windows improved/regressed: `{aggregate['ev_windows_improved']}` / `{aggregate['ev_windows_regressed']}`",
        f"- VNET trade count / PnL: `{aggregate['candidate_trade_count_sum']}` / `${aggregate['candidate_pnl_sum']:+,.2f}`",
        "",
        "## Parity",
        "",
        "No production universe or order path changed. Any promotion would require the candidate to enter the shared universe governance path used by both run.py and backtester.py.",
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def build_payload() -> dict[str, Any]:
    base_universe = sorted(set(get_universe()))
    candidates = sorted(set(CANDIDATE_TICKERS))
    expanded_universe = sorted(set(base_universe) | set(candidates))
    added_tickers = sorted(set(expanded_universe) - set(base_universe))
    if added_tickers != candidates:
        raise RuntimeError(f"Expected candidates to be new to the base universe: {added_tickers}")

    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    candidate_set = set(candidates)
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline on {window['snapshot']}")
        before_result = _run_engine(base_universe, window)
        print(f"[{label}] expanded with {','.join(candidates)}")
        after_result = _run_engine(expanded_universe, window)
        before = _metrics(before_result)
        after = _metrics(after_result)
        delta = _delta(after, before)
        candidate_stats = _candidate_stats(after_result.get("trades") or [], candidate_set)
        rows[label] = {
            "window": {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
                "state_note": window["state_note"],
            },
            "before": before,
            "after": after,
            "delta": delta,
            "candidate_trade_stats": candidate_stats,
            "entry_reason_counts_before": (
                before_result.get("entry_execution_attribution", {}).get("reason_counts", {})
            ),
            "entry_reason_counts_after": (
                after_result.get("entry_execution_attribution", {}).get("reason_counts", {})
            ),
        }
        print(
            f"[{label}] EV={delta['expected_value_score']:+.4f} "
            f"PnL={delta['total_pnl']:+.2f} trades={delta['trade_count']:+d} "
            f"candidate_pnl={candidate_stats['total_pnl']:+.2f}"
        )

    aggregate = _aggregate(rows)
    accepted = _accepted(aggregate)
    decision = "accepted_for_governance_review" if accepted else "rejected"
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "narrow_candidate_pool_expansion",
        "mechanism_family": "china_cloud_infrastructure_ads_candidate",
        "hypothesis": (
            "VNET may be a non-US cloud infrastructure continuation candidate "
            "that adds a different demand cycle than the already crowded US "
            "large-cap technology sleeve, without broadening into a noisy China "
            "ADR or speculative small-cap basket."
        ),
        "alpha_hypothesis": {
            "category": "entry / universe governance",
            "why_this_now": (
                "The strongest event-overlay direction remains blocked by sparse "
                "closed forward outcomes, and LLM soft-ranking lacks replayable "
                "samples. This tests a separate, narrow candidate-pool alpha "
                "using the fixed three-window OHLCV snapshots."
            ),
        },
        "historical_experiment_check": {
            "blocked_repeats": {
                "exp-20260505-009": (
                    "Rejected broad historical attention-list expansion. This "
                    "does not repeat broad watchlist growth; it isolates one "
                    "mechanism-grounded infrastructure ADS candidate."
                ),
                "exp-20260505-011": "Rejected consumer platform basket; VNET is cloud infrastructure, not consumer fintech/gaming.",
                "exp-20260505-032": "Rejected AKAM/ORCL enterprise infrastructure basket; this tests a different geography/demand cycle.",
                "exp-20260505-033": "Rejected cybersecurity infrastructure basket; VNET is not a security vendor basket.",
                "exp-20260506-014": "Rejected ORCL single-name; this avoids repeating US enterprise incumbent single-name mining.",
            },
            "mechanism_insight_check": (
                "Recent notes warn against broad noisy ticker additions, same-sample "
                "event retunes, and LLM ranking without samples. This replay changes "
                "only one candidate ticker and keeps production untouched."
            ),
            "why_not_simple_repeat": (
                "The tested variable is a single China cloud infrastructure ADS "
                "candidate, not a generic China basket, consumer platform basket, "
                "AI-infra pilot, ETF macro sleeve, or ranking/threshold retune."
            ),
        },
        "parameters": {
            "single_causal_variable": "candidate universe includes VNET",
            "candidate_tickers": candidates,
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "base_universe_count": len(base_universe),
            "expanded_universe_count": len(expanded_universe),
            "fresh_snapshots_reused": {label: row["snapshot"] for label, row in WINDOWS.items()},
            "locked_variables": [
                "signal_engine",
                "risk_engine",
                "portfolio_engine",
                "production_parity entry planning",
                "position sizing",
                "entry ordering",
                "exits",
                "add-ons",
                "LLM replay",
                "news replay",
                "event sleeves",
                "all numeric thresholds",
            ],
        },
        "date_range": {label: f"{row['start']} -> {row['end']}" for label, row in WINDOWS.items()},
        "market_regime_summary": {label: row["state_note"] for label, row in WINDOWS.items()},
        "before_metrics": {label: row["before"] for label, row in rows.items()},
        "after_metrics": {label: row["after"] for label, row in rows.items()},
        "delta_metrics": {
            "by_window": rows,
            "aggregate": aggregate,
        },
        "gate4": {
            "passed": accepted,
            "basis": (
                "Requires EV improvement in at least two of three fixed windows "
                "plus either aggregate EV improvement above 10% or aggregate PnL "
                "improvement above 5% with positive aggregate EV."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "promotion_requirement": (
                "If accepted, promote only through shared universe governance "
                "with run/backtester parity and forward replacement-value "
                "attribution."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking samples remain sparse.",
        },
        "rejection_reason": None if accepted else "Did not clear the three-window materiality and stability gate.",
        "next_action": (
            "If accepted, route through candidate governance before production. "
            "If rejected, do not mine more single-name China ADR candidates "
            "without a stronger ex-ante discriminator or forward evidence."
        ),
        "risk_of_change": (
            "A China ADS candidate can add geopolitical and liquidity risk and "
            "may compete with existing Technology winners for scarce slots."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still sample-limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "broad_watchlist": "Rejected by exp-20260505-009.",
            "same_sample_event_retuning": "Blocked by recent mechanism insights.",
            "AI_power_pilot_names": "Forward governance path already exists; same-sample replay is not enough.",
        },
        "related_files": [
            "quant/experiments/exp_20260506_017_vnet_china_cloud_candidate.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "decision": payload["decision"],
        "title": "VNET China cloud candidate",
        "summary": payload["next_action"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    })
    _write_artifact(payload)
    _write_jsonl(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
