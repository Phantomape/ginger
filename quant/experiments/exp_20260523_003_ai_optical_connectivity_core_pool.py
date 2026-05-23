"""exp-20260523-003: AI optical connectivity core-pool scout.

Alpha search on one causal variable: add the production-governed
`optical_connectivity` / ok-liquidity / full-history cohort to the core replay
universe. This uses the canonical-window observation-universe OHLCV snapshots
from exp-20260519-029, keeps all signal/ranking/sizing/exit rules fixed, and
does not change production watchlists or live orders.

No JavaScript is used.
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


EXPERIMENT_ID = "exp-20260523-003"
STEM = "ai_optical_connectivity_core_pool"
TRIAL_FAMILY = "governed_ai_infra_candidate_pool"
TARGET_SEGMENT = "optical_connectivity"
TARGET_SECTOR = "Technology"
SOURCE_UNIVERSE_STATE = REPO_ROOT / "data" / "daily" / "universe" / "universe_state_20260518.json"
SOURCE_OHLCV_EXPERIMENT_ID = "exp-20260519-029"

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
                    "data/experiments/exp-20260519-029/ohlcv/"
                    "exp-20260519-029_late_strong_current_universe_ohlcv.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": (
                    "data/experiments/exp-20260519-029/ohlcv/"
                    "exp-20260519-029_mid_weak_current_universe_ohlcv.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": (
                    "data/experiments/exp-20260519-029/ohlcv/"
                    "exp-20260519-029_old_thin_current_universe_ohlcv.json"
                ),
            },
        ),
    ]
)


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


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {"passed": False, "reason": "open_positions.json missing"}
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows = payload if isinstance(payload, list) else payload.get("positions", [])
    missing: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        for field in ("entry_date", "target_price"):
            if row.get(field) in (None, ""):
                missing.append({"index": index, "ticker": row.get("ticker"), "field": field})
    return {
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "checked_positions": len(rows or []),
        "missing_required_fields": missing,
        "passed": not missing,
    }


def _target_universe() -> dict[str, Any]:
    state = _load_json(SOURCE_UNIVERSE_STATE)
    core = {str(ticker).upper() for ticker in state.get("core_trade_universe") or []}
    records = state.get("records") or {}
    selected: list[str] = []
    selected_records: dict[str, Any] = {}
    excluded: dict[str, list[str]] = {}
    for ticker, record in sorted(records.items()):
        if not isinstance(record, dict):
            continue
        symbol = str(ticker).upper()
        reasons: list[str] = []
        if record.get("theme_segment") != TARGET_SEGMENT:
            reasons.append("not_target_segment")
        if record.get("liquidity_tier") != "ok":
            reasons.append("liquidity_not_ok")
        if record.get("history_class") != "full_history":
            reasons.append("not_full_history")
        if symbol in core:
            reasons.append("already_core")
        if reasons:
            if record.get("theme_segment") == TARGET_SEGMENT:
                excluded[symbol] = reasons
            continue
        selected.append(symbol)
        selected_records[symbol] = {
            key: record.get(key)
            for key in (
                "status",
                "theme",
                "theme_segment",
                "liquidity_tier",
                "history_class",
                "first_trade_allowed_as_of",
                "max_risk_scalar",
                "event_guard_profile",
                "source",
                "source_reason",
            )
        }
    return {
        "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
        "as_of": state.get("as_of"),
        "selection_rule": (
            "records.theme_segment == optical_connectivity and liquidity_tier == ok "
            "and history_class == full_history and not already in core"
        ),
        "target_tickers": selected,
        "target_records": selected_records,
        "excluded_target_segment_records": excluded,
    }


def _snapshot_coverage(target_tickers: list[str]) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    passed = True
    for label, spec in WINDOWS.items():
        snapshot_path = REPO_ROOT / spec["snapshot"]
        payload = _load_json(snapshot_path)
        ohlcv = payload.get("ohlcv") or {}
        ticker_rows = {ticker: len(ohlcv.get(ticker) or []) for ticker in target_tickers}
        missing = [ticker for ticker, count in ticker_rows.items() if count <= 0]
        if missing:
            passed = False
        coverage[label] = {
            "snapshot": spec["snapshot"],
            "ticker_row_counts": ticker_rows,
            "missing_tickers": missing,
        }
    return {"passed": passed, "by_window": coverage}


@contextmanager
def _target_sector_patch(target_tickers: list[str]):
    original = {ticker: risk_engine.SECTOR_MAP.get(ticker) for ticker in target_tickers}
    for ticker in target_tickers:
        risk_engine.SECTOR_MAP[ticker] = TARGET_SECTOR
    try:
        yield
    finally:
        for ticker, value in original.items():
            if value is None:
                risk_engine.SECTOR_MAP.pop(ticker, None)
            else:
                risk_engine.SECTOR_MAP[ticker] = value


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


def _risk_distribution(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") or []
    pnl_pcts = [
        float(trade.get("pnl_pct_net"))
        for trade in trades
        if trade.get("pnl_pct_net") is not None
    ]
    pnls = [float(trade.get("pnl") or 0.0) for trade in trades]
    max_consecutive_losses = 0
    current_losses = 0
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


def _target_trades(result: dict[str, Any], target_tickers: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker") or "").upper()
        if ticker not in target_tickers:
            continue
        rows.append(
            {
                "ticker": ticker,
                "sector": trade.get("sector"),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "entry_price": _round(trade.get("entry_price"), 4),
                "exit_price": _round(trade.get("exit_price"), 4),
                "shares": trade.get("shares"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
            }
        )
    return rows


def _target_trade_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_count: dict[str, int] = {}
    by_ticker_pnl: dict[str, float] = {}
    for trades in target_trades_by_window.values():
        for trade in trades:
            ticker = str(trade["ticker"])
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] = by_ticker_count.get(ticker, 0) + 1
            by_ticker_pnl[ticker] = round(by_ticker_pnl.get(ticker, 0.0) + pnl, 2)
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = round(sum(positive.values()), 2)
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    top5_share = None
    if positive_total > 0 and positive:
        top5_share = round(sum(sorted(positive.values(), reverse=True)[:5]) / positive_total, 6)
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_ticker_count": by_ticker_count,
        "by_ticker_pnl": by_ticker_pnl,
        "positive_by_ticker_pnl": positive,
        "max_single_positive_pnl_share": max_positive_share,
        "top5_positive_pnl_share": top5_share,
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {target_trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                target_trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AI Optical Connectivity Core-Pool Scout",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: add the governed optical-connectivity cohort to the core replay universe.",
            "",
            "## Trial Accounting",
            "",
            f"- trial_family: `{payload['trial_family']}`",
            f"- changed_variable: `{payload['changed_variable']}`",
            f"- prior_trial_count: `{payload['prior_trial_count']}`",
            f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
            f"- new_evidence_type: `{payload['new_evidence_type']}`",
            "",
            "## Target Cohort",
            "",
            ", ".join(f"`{ticker}`" for ticker in payload["parameters"]["target_tickers"]),
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
            "No production watchlist, shared policy, run adapter, or order path changed. A positive result requires shared universe/taxonomy implementation and parity tests before any live/default behavior changes.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_payload() -> dict[str, Any]:
    gate2_open_positions = _audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    target_universe = _target_universe()
    target_tickers = target_universe["target_tickers"]
    if not target_tickers:
        raise RuntimeError("No target tickers selected from universe state")
    coverage = _snapshot_coverage(target_tickers)
    if not coverage["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV coverage failed: {coverage}")

    base_universe = sorted(get_universe())
    after_universe = sorted(set(base_universe) | set(target_tickers))
    before_results: dict[str, dict[str, Any]] = {}
    after_results: dict[str, dict[str, Any]] = {}
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_set = set(target_tickers)

    with _target_sector_patch(target_tickers):
        for label in WINDOWS:
            print(f"[{label}] baseline core universe")
            before_results[label] = _run_window(label, base_universe)
            print(f"[{label}] core + {TARGET_SEGMENT}")
            after_results[label] = _run_window(label, after_universe)
            before_metrics[label] = _metrics(before_results[label])
            after_metrics[label] = _metrics(after_results[label])
            target_trades_by_window[label] = _target_trades(after_results[label], target_set)

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
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0) for label in WINDOWS
    )
    target_summary = _target_trade_summary(target_trades_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= 0.50
        and target_summary["top5_positive_pnl_share"] is not None
        and target_summary["top5_positive_pnl_share"] <= 0.80
    )

    gate4_passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and target_summary["total_trade_count"] >= 6
        and len(target_windows) >= 2
        and max_drawdown_worse <= 0.005
        and aggregate_after["min_survival_rate"] >= 0.05
        and concentration_passed
    )
    decision = (
        "positive_replay_requires_shared_universe_implementation"
        if gate4_passed
        else "rejected_ai_optical_connectivity_core_pool"
    )
    rejection_reason = None
    if not gate4_passed:
        rejection_reason = (
            "AI optical-connectivity cohort did not clear the direct candidate-pool gate: "
            "requires positive aggregate EV/PnL, at least two improved windows, no EV-regressed "
            "window, >=6 target trades across >=2 windows, drawdown drift <=0.5pp, survival >=5%, "
            "and target positive-PnL concentration within guardrails."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "AI optical-connectivity names with production-governed ok liquidity and full "
            "history may add cleaner candidate-pool alpha than single-ticker CIEN/MRVL "
            "promotion attempts, because the cohort captures AI network buildout demand "
            "without broad noisy watchlist expansion."
        ),
        "change_type": "candidate_pool_shadow",
        "changed_variable": "ai_optical_connectivity_core_universe_membership",
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260510-011",
            "exp-20260519-014",
            "exp-20260520-019",
            "exp-20260520-040",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "canonical_aligned_observation_universe_ohlcv",
        "backtest_protocol": {
            "source": "docs/backtesting.md three-window replay using exp-20260519-029 observation-universe snapshots",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_segment": TARGET_SEGMENT,
            "target_sector_patch": TARGET_SECTOR,
            "target_tickers": target_tickers,
            "target_universe": target_universe,
            "base_universe_count": len(base_universe),
            "after_universe_count": len(after_universe),
            "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
            "locked_variables": [
                "signal rules",
                "ranking",
                "sizing policy",
                "exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "all non-target ticker membership",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": 2,
                "max_ev_regressed_windows": 0,
                "min_target_trades": 6,
                "min_target_windows": 2,
                "max_drawdown_worse": 0.005,
                "max_single_target_positive_pnl_share": 0.50,
                "max_top5_target_positive_pnl_share": 0.80,
            },
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": "entry/candidate_pool: governed AI optical-connectivity names may add trend/breakout opportunities with less noise than broad watchlist expansion.",
            "2_history_check": {
                "exp-20260510-011": "MRVL-only was rejected, EV regressed in all windows.",
                "exp-20260519-014": "AI infra segment shadow had positive variants but baseline-alignment failed on cached snapshots.",
                "exp-20260520-019": "CIEN-only was positive but rejected for one executed trade.",
                "exp-20260520-040": "AGX direct core promotion failed with zero AGX executed trades.",
            },
            "3_single_causal_variable": "membership of one production-visible optical-connectivity cohort in the replay core universe.",
            "4_acceptance_standard": "canonical three-window before/after with positive aggregate EV/PnL, no EV-regressed window, target sample/concentration/risk guards, and survival >=5%.",
            "5_reproducibility": ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260523_003_ai_optical_connectivity_core_pool.py",
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": aggregate_before,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "ohlcv_coverage": coverage,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "universe_state records.theme_segment/liquidity_tier/history_class",
                "target OHLCV rows in all three exp-20260519-029 snapshots",
                "risk_engine.SECTOR_MAP target tickers patched to Technology in replay",
            ],
            "passed": gate2_open_positions["passed"] and coverage["passed"],
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
            "target_trade_count": target_summary["total_trade_count"],
            "target_trade_count_min": 6,
            "target_windows": target_windows,
            "target_window_count_min": 2,
            "max_drawdown_worse": _round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": 0.005,
            "survival_guard_passed": aggregate_after["min_survival_rate"] >= 0.05,
            "target_concentration": {
                "passed": concentration_passed,
                "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
                "max_single_positive_pnl_share_guardrail": 0.50,
                "top5_positive_pnl_share": target_summary["top5_positive_pnl_share"],
                "top5_positive_pnl_share_guardrail": 0.80,
            },
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
        "target_trade_summary": target_summary,
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
                "If accepted later, implement through shared universe governance and "
                "sector taxonomy visible to both run.py and backtester.py, add parity "
                "coverage, then rerun canonical windows."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking due sparse attribution; skipped SEC fact/tone and "
            "event-source scalars due recent failed near-neighbor tests; skipped "
            "state-surface and broad-market notional/profile retunes due strict gate and "
            "anti-repeat risk. This uses a production-visible candidate-pool cohort with "
            "canonical-aligned OHLCV instead of adding arbitrary noisy tickers."
        ),
        "known_risks": [
            "Candidate-pool expansion uses current governed universe records, so live promotion still needs PIT universe governance.",
            "Sector taxonomy for target names is patched in replay only and would need shared implementation if promoted.",
            "Same-family AI infra candidate-pool experiments have moderate multiple-testing risk.",
        ],
        "interpretation": (
            "The cohort cleared replay gates but is not production-enabled; implement shared universe/taxonomy before any live behavior."
            if gate4_passed
            else "The cohort did not clear the direct core-pool gate; keep optical-connectivity names in governed pilot/research paths."
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Implement shared universe/taxonomy and rerun canonical replay before promotion."
            if gate4_passed
            else "Collect forward AI optical pilot/research replacement-value outcomes or a stronger source/event-quality field before retrying this cohort."
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
            "title": "AI optical connectivity core-pool scout",
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
                "target_trade_summary": payload["target_trade_summary"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
