"""exp-20260505-011: consumer digital platform sub-basket replay.

Alpha search. This is the narrow retry allowed by the rejected broad
historical-watchlist expansion: test one mechanism-grounded sub-basket instead
of adding many noisy tickers. It does not alter production universe, ranking,
sizing, exits, LLM, news, or event sleeves.
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


EXPERIMENT_ID = "exp-20260505-011"
SUB_BASKET = ["HOOD", "RBLX", "SOFI"]
SOURCE_EXPERIMENT_ID = "exp-20260505-009"

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
OUT_JSON = OUT_DIR / "consumer_digital_platform_subbasket.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_consumer_digital_platform_subbasket.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
PLAYBOOK = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


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


def _trade_stats(trades: list[dict[str, Any]], tickers: set[str]) -> dict[str, Any]:
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
        "max_sharpe_daily_delta": _round(
            max(row["delta"].get("sharpe_daily", 0.0) for row in rows.values()), 6
        ),
        "trade_count_delta_sum": sum(row["delta"].get("trade_count", 0) for row in rows.values()),
        "win_rate_delta_min": _round(
            min(row["delta"].get("win_rate", 0.0) for row in rows.values()), 6
        ),
        "subbasket_trade_count_sum": sum(row["subbasket_trade_stats"]["trade_count"] for row in rows.values()),
        "subbasket_pnl_sum": _round(
            sum(row["subbasket_trade_stats"]["total_pnl"] or 0.0 for row in rows.values()), 2
        ),
    }


def _accepted(aggregate: dict[str, Any]) -> bool:
    majority_ev = aggregate["ev_windows_improved"] >= 2
    material = (
        (aggregate["expected_value_score_delta_pct"] or 0.0) > 0.10
        or (aggregate["total_pnl_delta_pct"] or 0.0) > 0.05
        or aggregate["max_drawdown_delta_max"] < -0.01
        or aggregate["max_sharpe_daily_delta"] > 0.10
        or (
            aggregate["trade_count_delta_sum"] > 0
            and aggregate["win_rate_delta_min"] >= 0
        )
    )
    return bool(majority_ev and material)


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
        f"# {EXPERIMENT_ID} Consumer Digital Platform Sub-basket",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Sub-basket",
        "",
        ", ".join(f"`{ticker}`" for ticker in payload["parameters"]["subbasket_tickers"]),
        "",
        "## Three-window deltas",
        "",
        "| Window | EV delta | PnL delta | SharpeD delta | DD delta | WR delta | Trades delta | Basket trades | Basket PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in payload["delta_metrics"]["by_window"].items():
        delta = row["delta"]
        stats = row["subbasket_trade_stats"]
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
        f"- Sub-basket trade count / PnL: `{aggregate['subbasket_trade_count_sum']}` / `${aggregate['subbasket_pnl_sum']:+,.2f}`",
        "",
        "## Parity",
        "",
        "No production universe or order path changed. A promotion would need universe governance or a default-off pilot adapter before live orders.",
        "",
    ])
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_playbook(payload: dict[str, Any]) -> None:
    marker = "## Recent mechanism insights"
    aggregate = payload["delta_metrics"]["aggregate"]
    entry = (
        "\n"
        f"- `{EXPERIMENT_ID}` ({payload['decision']}): Narrow consumer digital "
        f"platform sub-basket `{', '.join(SUB_BASKET)}` was replayed after the "
        "broad historical-watchlist expansion failed. "
        f"Aggregate EV delta {aggregate['expected_value_score_delta_sum']} "
        f"({aggregate['expected_value_score_delta_pct']:.2%}), PnL delta "
        f"${aggregate['total_pnl_delta_sum']}. "
        "Do not promote directly to the core universe; a valid next step is "
        "universe-governance or default-off pilot treatment with forward "
        "replacement-value attribution.\n"
    )
    text = PLAYBOOK.read_text(encoding="utf-8")
    if f"`{EXPERIMENT_ID}`" in text:
        return
    if marker in text:
        text = text.replace(marker, marker + entry, 1)
    else:
        text = text + "\n" + marker + "\n" + entry
    PLAYBOOK.write_text(text, encoding="utf-8")


def build_payload() -> dict[str, Any]:
    base_universe = sorted(set(get_universe()))
    subbasket = sorted(set(SUB_BASKET))
    expanded_universe = sorted(set(base_universe) | set(subbasket))
    added_tickers = sorted(set(expanded_universe) - set(base_universe))
    if added_tickers != subbasket:
        raise RuntimeError(f"Expected all sub-basket tickers to be new: {added_tickers}")

    rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    subbasket_set = set(subbasket)
    for label, window in WINDOWS.items():
        print(f"[{label}] baseline on {window['snapshot']}")
        before_result = _run_engine(base_universe, window)
        print(f"[{label}] expanded with {','.join(subbasket)}")
        after_result = _run_engine(expanded_universe, window)
        before = _metrics(before_result)
        after = _metrics(after_result)
        delta = _delta(after, before)
        stats = _trade_stats(after_result.get("trades") or [], subbasket_set)
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
            "subbasket_trade_stats": stats,
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
            f"basket_pnl={stats['total_pnl']:+.2f}"
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
        "mechanism_family": "consumer_digital_platform_universe_subbasket",
        "hypothesis": (
            "A small US consumer digital platform basket may be a better "
            "extension surface than the rejected broad historical watchlist: "
            "HOOD, RBLX, and SOFI are liquid engagement/platform names where "
            "existing A/B momentum and breakout rules may capture reflexive "
            "repricing without adding leveraged, macro, or low-quality tickers."
        ),
        "alpha_hypothesis": {
            "category": "entry / universe governance",
            "why_this_now": (
                "LLM soft-ranking and event-bundle promotion are waiting for "
                "forward samples. The broad attention-list expansion failed, "
                "but its own retry condition allows a much smaller "
                "mechanism-grounded sub-basket with stable cross-window evidence."
            ),
        },
        "historical_experiment_check": {
            "blocked_repeats": {
                "exp-20260505-009": (
                    "Rejected broad historical attention-list expansion. This "
                    "does not repeat the broad list; it tests one narrow "
                    "sub-basket with the same fresh snapshots."
                ),
                "exp-20260504-028": "Rejected broad macro ETF candidate-pool expansion.",
                "exp-20260505-006": "Rejected stricter sector-crowding rule.",
                "exp-20260505-010": "Rejected Form 4 sale-pressure de-risking.",
            },
            "mechanism_insight_check": (
                "Recent insights prohibit more noisy ticker growth. This test "
                "uses a named small basket and keeps production unchanged."
            ),
            "why_not_simple_repeat": (
                "The variable is not broad universe growth, a macro ETF basket, "
                "a sector cap, or a threshold retune; it is a three-name "
                "governance candidate replay."
            ),
        },
        "parameters": {
            "single_causal_variable": "candidate universe includes HOOD/RBLX/SOFI sub-basket",
            "subbasket_tickers": subbasket,
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
                "Requires material aggregate EV/PnL/Sharpe/drawdown/trade-count "
                "improvement and EV improvement in at least two of three fixed windows."
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
                "If retained, promote only through universe governance or a "
                "default-off pilot sleeve with run/backtester parity and forward "
                "replacement-value attribution."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "Production-aligned LLM soft-ranking samples remain sparse.",
        },
        "rejection_reason": None if accepted else "Did not clear three-window materiality and stability gate.",
        "next_action": (
            "If accepted, build a default-off pilot/governance queue before any "
            "live core promotion. If rejected, do not mine more broad-watchlist "
            "subsets without a stronger ex-ante discriminator."
        ),
        "risk_of_change": (
            "The sub-basket can add high-beta consumer/platform exposure and may "
            "consume scarce slots during weak tapes; production promotion needs "
            "forward replacement-value evidence."
        ),
        "why_not_other_attractive_points": {
            "LLM_soft_ranking": "Still sample-limited.",
            "event_bundle_promotion": "Needs closed forward paper outcomes.",
            "broad_watchlist": "Rejected by exp-20260505-009.",
            "same_sample_event_retuning": "Blocked by recent mechanism insights.",
        },
        "related_files": [
            "quant/experiments/exp_20260505_011_consumer_digital_platform_subbasket.py",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "docs/experiment_log.jsonl",
            "docs/alpha-optimization-playbook.md",
        ],
    }


def main() -> int:
    payload = build_payload()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["generated_at"],
        "decision": payload["decision"],
        "title": "Consumer digital platform sub-basket",
        "summary": payload["next_action"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"]["aggregate"],
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
    }
    _write_json(TICKET_JSON, ticket)
    _write_artifact(payload)
    _append_jsonl(EXPERIMENT_LOG_JSONL, payload)
    _update_playbook(payload)
    print(json.dumps({
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "aggregate": payload["delta_metrics"]["aggregate"],
        "out_json": str(OUT_JSON.relative_to(REPO_ROOT)),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
