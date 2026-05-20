"""exp-20260520-040: AGX core candidate-pool scout.

Alpha search on one causal variable: add AGX as a correctly classified
Industrials candidate to the core universe replay, without changing ranking,
sizing, exits, slots, heat, LLM/news, or production watchlists.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260520-040"
STEM = "agx_core_candidate_pool"
TARGET_TICKER = "AGX"
TARGET_SECTOR = "Industrials"
SOURCE_BATCH_EXPERIMENT_ID = "exp-20260520-007"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": (
                    "data/experiments/exp-20260520-007/ohlcv/"
                    "exp-20260520-007_late_strong_core_promotion_ohlcv.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": (
                    "data/experiments/exp-20260520-007/ohlcv/"
                    "exp-20260520-007_mid_weak_core_promotion_ohlcv.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": (
                    "data/experiments/exp-20260520-007/ohlcv/"
                    "exp-20260520-007_old_thin_core_promotion_ohlcv.json"
                ),
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    rows = (
        path.read_text(encoding="utf-8", errors="replace").splitlines()
        if path.exists()
        else []
    )
    kept = [row for row in rows if compact not in row and pretty not in row]
    kept.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "open_positions.json missing"}
    payload = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    positions = payload if isinstance(payload, list) else payload.get("positions", [])
    missing: list[dict[str, Any]] = []
    for idx, position in enumerate(positions or []):
        if not isinstance(position, dict):
            continue
        for field in ("entry_date", "target_price"):
            if position.get(field) in (None, ""):
                missing.append({"index": idx, "ticker": position.get("ticker"), "field": field})
    return {
        "passed": not missing,
        "checked_positions": len(positions or []),
        "missing_required_fields": missing,
    }


@contextmanager
def _agx_sector_patch():
    original = risk_engine.SECTOR_MAP.get(TARGET_TICKER)
    risk_engine.SECTOR_MAP[TARGET_TICKER] = TARGET_SECTOR
    try:
        yield
    finally:
        if original is None:
            risk_engine.SECTOR_MAP.pop(TARGET_TICKER, None)
        else:
            risk_engine.SECTOR_MAP[TARGET_TICKER] = original


def _risk_distribution(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") or []
    pnl_pcts = [
        float(trade.get("pnl_pct_net"))
        for trade in trades
        if trade.get("pnl_pct_net") is not None
    ]
    pnls = [float(trade.get("pnl") or 0.0) for trade in trades]
    current_losses = 0
    max_consecutive_losses = 0
    for pnl in pnls:
        if pnl < 0:
            current_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
        else:
            current_losses = 0
    losses = sorted(pnl for pnl in pnls if pnl < 0)
    total_loss = abs(sum(losses))
    worst_three = abs(sum(losses[:3]))
    return {
        "worst_trade_pct": _round(min(pnl_pcts), 6) if pnl_pcts else None,
        "max_consecutive_losses": max_consecutive_losses,
        "tail_loss_share": _round(worst_three / total_loss, 6) if total_loss else 0.0,
    }


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
        **_risk_distribution(result),
    }


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in sorted(set(after) | set(before)):
        a = after.get(key)
        b = before.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived", "max_consecutive_losses"}:
                out[key] = int(a - b)
            else:
                out[key] = _round(a - b, 6)
    return out


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": _round(
            sum(float(row.get("expected_value_score") or 0.0) for row in rows.values()),
            6,
        ),
        "total_pnl_sum": _round(
            sum(float(row.get("total_pnl") or 0.0) for row in rows.values()),
            2,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in rows.values()),
        "min_survival_rate": min(float(row.get("survival_rate") or 0.0) for row in rows.values()),
        "max_drawdown_pct_max": max(float(row.get("max_drawdown_pct") or 0.0) for row in rows.values()),
    }


def _run_window(label: str, universe: list[str]) -> dict[str, Any]:
    spec = WINDOWS[label]
    return BacktestEngine(
        sorted(set(universe)),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
    ).run()


def _target_trades(result: dict[str, Any]) -> list[dict[str, Any]]:
    trades = []
    for trade in result.get("trades") or []:
        if str(trade.get("ticker") or "").upper() != TARGET_TICKER:
            continue
        trades.append(
            {
                "ticker": trade.get("ticker"),
                "sector": trade.get("sector"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "entry_price": trade.get("entry_price"),
                "exit_price": trade.get("exit_price"),
                "shares": trade.get("shares"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
            }
        )
    return trades


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | AGX trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AGX Core Candidate-Pool Scout",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: AGX membership in the core replay universe, with required Industrials taxonomy applied for correct risk classification.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "No production watchlist, shared policy, run adapter, or order path changed. A positive result would require a shared watchlist and sector-map promotion plus another canonical replay.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_payload() -> dict[str, Any]:
    gate2 = _audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base_universe = sorted(get_universe())
    after_universe = sorted(set(base_universe) | {TARGET_TICKER})
    before_results: dict[str, dict[str, Any]] = {}
    after_results: dict[str, dict[str, Any]] = {}
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    with _agx_sector_patch():
        for label in WINDOWS:
            print(f"[{label}] baseline universe")
            before_results[label] = _run_window(label, base_universe)
            print(f"[{label}] {TARGET_TICKER} universe")
            after_results[label] = _run_window(label, after_universe)
            before_metrics[label] = _metrics(before_results[label])
            after_metrics[label] = _metrics(after_results[label])
            target_trades_by_window[label] = _target_trades(after_results[label])

    by_window_delta = OrderedDict(
        (label, _delta(after_metrics[label], before_metrics[label])) for label in WINDOWS
    )
    aggregate_before = _aggregate(before_metrics)
    aggregate_after = _aggregate(after_metrics)
    aggregate_delta = _delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in WINDOWS
        if (after_metrics[label]["expected_value_score"] or 0)
        > (before_metrics[label]["expected_value_score"] or 0)
    ]
    regressed = [
        label
        for label in WINDOWS
        if (after_metrics[label]["expected_value_score"] or 0)
        < (before_metrics[label]["expected_value_score"] or 0)
    ]
    target_trade_count = sum(len(rows) for rows in target_trades_by_window.values())
    target_pnl = _round(
        sum(float(trade.get("pnl") or 0.0) for rows in target_trades_by_window.values() for trade in rows),
        2,
    )
    target_windows = [label for label, rows in target_trades_by_window.items() if rows]
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0) for label in WINDOWS
    )
    gate4_passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and target_trade_count >= 3
        and len(target_windows) >= 2
        and max_drawdown_worse <= 0.005
        and aggregate_after["min_survival_rate"] >= 0.05
    )
    decision = (
        "accepted_for_shared_watchlist_implementation"
        if gate4_passed
        else "rejected_agx_core_candidate_pool"
    )
    rejection_reason = None
    if not gate4_passed:
        rejection_reason = (
            "AGX did not clear the direct core candidate-pool promotion gate: "
            "requires positive aggregate EV/PnL, at least two improved windows, "
            "no EV-regressed window, >=3 AGX trades across >=2 windows, and drawdown drift <=0.5pp."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "AGX may be the cleaner industrial-infrastructure portion of the rejected "
            "six-name broad-market core promotion batch. Testing AGX alone with correct "
            "Industrials taxonomy checks candidate-pool alpha without adding a noisy basket."
        ),
        "change_type": "candidate_pool_shadow",
        "changed_variable": "agx_core_universe_membership",
        "trial_family": "broad_market_candidate_pool_governance",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260520-007",
            "exp-20260520-019",
            "exp-20260520-021",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "single_ticker_correct_sector_replay",
        "backtest_protocol": {
            "source": "docs/backtesting.md three-window replay using exp-20260520-007 AGX-augmented snapshots",
            "windows": WINDOWS,
        },
        "parameters": {
            "target_ticker": TARGET_TICKER,
            "target_sector": TARGET_SECTOR,
            "base_universe_count": len(base_universe),
            "after_universe_count": len(after_universe),
            "source_batch_experiment_id": SOURCE_BATCH_EXPERIMENT_ID,
            "locked_variables": [
                "signal rules",
                "ranking",
                "sizing policy",
                "exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "all non-AGX ticker membership",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": "entry / candidate_pool: AGX may be the isolated industrial-infrastructure alpha from the rejected six-name broad-market batch.",
            "2_history_check": {
                "exp-20260520-007": "six-name direct promotion rejected; AGX was the positive late_strong contributor but batch damaged mid_weak/old_thin.",
                "exp-20260520-019": "CIEN-only positive result was rejected for one-trade evidence.",
                "exp-20260520-021": "CIEN required correct Technology taxonomy and then produced no selectable trades.",
            },
            "3_single_causal_variable": "AGX core universe membership; Industrials taxonomy is a required field correction for the replay, not an alpha selector.",
            "4_acceptance_standard": "canonical three-window before/after; positive aggregate EV/PnL, >=2 improved windows, no EV-regressed window, survival >=5%, >=3 AGX trades across >=2 windows, drawdown drift <=0.5pp.",
            "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260520_040_agx_core_candidate_pool.py",
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "OHLCV AGX rows in all three augmented snapshots",
                "risk_engine.SECTOR_MAP AGX=Industrials in replay",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_after_survival_rate": aggregate_after["min_survival_rate"],
            "passed": aggregate_after["min_survival_rate"] >= 0.05,
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "target_trade_count": target_trade_count,
            "target_trade_count_min": 3,
            "target_windows": target_windows,
            "target_window_count_min": 2,
            "max_drawdown_worse": _round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": 0.005,
            "survival_guard_passed": aggregate_after["min_survival_rate"] >= 0.05,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_trade_count": target_trade_count,
        "target_total_pnl": target_pnl,
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "promotion_requirement": (
                "If accepted, update shared watchlist and AGX sector taxonomy used by both "
                "run.py and backtester.py, add parity coverage, then rerun canonical windows."
            ),
        },
        "why_not_other_changes": (
            "The SEC buyback field was zero-sample; LLM soft-ranking remains sparse; "
            "state-surface/broad-market scalar retunes are anti-repeat/strict-gated. "
            "A single correctly classified industrial-infrastructure candidate tests "
            "candidate-pool expansion without adding a noisy ticker basket."
        ),
        "known_risks": [
            "Single-ticker candidate-pool experiments have moderate multiple-testing risk.",
            "The augmented snapshots are replay artifacts, not proof of production PIT availability.",
            "A positive replay cannot change live watchlists without shared taxonomy and parity tests.",
        ],
        "interpretation": (
            "AGX cleared the replay gate and is ready for shared implementation."
            if gate4_passed
            else "AGX did not clear the direct core candidate-pool gate; keep it out of the live core watchlist."
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            None
            if gate4_passed
            else "Collect forward broad-market paper outcomes or a stronger industrial-infrastructure field before retrying AGX/core promotion."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "AGX core candidate-pool scout",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4": payload["gate4"],
                "target_trade_count": payload["target_trade_count"],
                "target_total_pnl": payload["target_total_pnl"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
