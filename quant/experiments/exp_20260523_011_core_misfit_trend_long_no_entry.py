"""exp-20260523-011: core-misfit trend_long no-entry shadow.

Alpha search on one causal variable: set post-sizing shares to zero for the
existing CORE_MISFIT_PAPER ticker set when the source strategy is trend_long.
This tests reduced long exposure, not a live short or a new candidate pool.

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

import exp_20260523_009_ai_power_datacenter_core_pool as base  # noqa: E402


EXPERIMENT_ID = "exp-20260523-011"
STEM = "core_misfit_trend_long_no_entry"
TRIAL_FAMILY = "core_misfit_long_risk_governance"
TARGET_TICKERS = ("DDOG", "ISRG", "TSM", "V")
TARGET_STRATEGY = "trend_long"
HAIRCUT_MULTIPLIER = 0.0

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)


def _repo_rel(path: Path | str) -> str:
    value = Path(path) if not isinstance(path, Path) else path
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(base._safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=True, sort_keys=True)
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


def _snapshot_coverage(target_tickers: list[str]) -> dict[str, Any]:
    coverage: dict[str, Any] = {}
    passed = True
    for label, spec in WINDOWS.items():
        snapshot_path = REPO_ROOT / spec["snapshot"]
        payload = base._load_json(snapshot_path)
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


def _rescale_sizing(sig: dict[str, Any], portfolio_value: float, multiplier: float) -> None:
    sizing = sig.get("sizing")
    if not isinstance(sizing, dict):
        return

    sizing["core_misfit_trend_long_haircut_multiplier_applied"] = multiplier
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return

    entry = float(sizing.get("entry_price") or sig.get("entry_price") or 0.0)
    if entry <= 0:
        return

    new_shares = int(math.floor(old_shares * multiplier))
    if new_shares >= old_shares:
        return

    net_risk_per_share = float(sizing.get("net_risk_per_share") or 0.0)
    position_value = entry * new_shares
    risk_amount = net_risk_per_share * new_shares
    sizing["core_misfit_trend_long_baseline_shares"] = old_shares
    sizing["core_misfit_trend_long_new_shares"] = new_shares
    sizing["shares_to_buy"] = new_shares
    sizing["position_value_usd"] = round(position_value, 2)
    sizing["position_pct_of_portfolio"] = (
        round(position_value / portfolio_value, 4) if portfolio_value else 0.0
    )
    sizing["risk_amount_usd"] = round(risk_amount, 2)
    sizing["risk_pct"] = risk_amount / portfolio_value if portfolio_value else 0.0


@contextmanager
def _core_misfit_trend_long_haircut(multiplier: float):
    import portfolio_engine  # noqa: E402

    original_size_signals = portfolio_engine.size_signals
    target_set = set(TARGET_TICKERS)

    def wrapped_size_signals(signals, portfolio_value, risk_pct=None):
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        for sig in sized:
            ticker = str(sig.get("ticker") or "").upper()
            if ticker in target_set and sig.get("strategy") == TARGET_STRATEGY:
                _rescale_sizing(sig, portfolio_value, multiplier)
        return sized

    portfolio_engine.size_signals = wrapped_size_signals
    try:
        yield
    finally:
        portfolio_engine.size_signals = original_size_signals


def _run_window(label: str, *, haircut: bool) -> dict[str, Any]:
    spec = WINDOWS[label]
    engine = base.BacktestEngine(
        sorted(base.get_universe()),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
        include_entry_candidate_events=True,
    )
    if not haircut:
        return engine.run()
    with _core_misfit_trend_long_haircut(HAIRCUT_MULTIPLIER):
        return engine.run()


def _target_trades(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_set = set(TARGET_TICKERS)
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker") or "").upper()
        if ticker not in target_set or trade.get("strategy") != TARGET_STRATEGY:
            continue
        rows.append(
            {
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "shares": trade.get("shares"),
                "pnl": base._round(trade.get("pnl"), 2),
                "pnl_pct_net": base._round(trade.get("pnl_pct_net"), 6),
            }
        )
    return rows


def _target_candidate_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_set = set(TARGET_TICKERS)
    for event in result.get("entry_candidate_events") or []:
        ticker = str(event.get("ticker") or "").upper()
        if ticker not in target_set or event.get("strategy") != TARGET_STRATEGY:
            continue
        snapshot = event.get("signal_snapshot") or {}
        sizing = snapshot.get("sizing") or {}
        rows.append(
            {
                "date": event.get("date"),
                "ticker": ticker,
                "strategy": event.get("strategy"),
                "decision": event.get("decision"),
                "candidate_rank": event.get("candidate_rank"),
                "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
                "shares_to_buy": sizing.get("shares_to_buy"),
                "risk_pct": sizing.get("risk_pct"),
                "risk_multipliers": sizing.get("risk_multipliers"),
            }
        )
    return rows


def _summarize_target_trades(by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_count: dict[str, int] = {}
    by_ticker_pnl: dict[str, float] = {}
    for rows in by_window.values():
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            pnl = float(row.get("pnl") or 0.0)
            by_ticker_count[ticker] = by_ticker_count.get(ticker, 0) + 1
            by_ticker_pnl[ticker] = round(by_ticker_pnl.get(ticker, 0.0) + pnl, 2)
    return {
        "trade_count": sum(by_ticker_count.values()),
        "windows_with_trades": [label for label, rows in by_window.items() if rows],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_ticker_count": by_ticker_count,
        "by_ticker_pnl": by_ticker_pnl,
    }


def _summarize_candidate_events(by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_decision: dict[str, int] = {}
    by_ticker_decision: dict[str, dict[str, int]] = {}
    for rows in by_window.values():
        for row in rows:
            decision = str(row.get("decision") or "unknown")
            ticker = str(row.get("ticker") or "").upper()
            by_decision[decision] = by_decision.get(decision, 0) + 1
            ticker_row = by_ticker_decision.setdefault(ticker, {})
            ticker_row[decision] = ticker_row.get(decision, 0) + 1
    return {
        "candidate_event_count": sum(by_decision.values()),
        "windows_with_target_candidates": [
            label for label, rows in by_window.items() if rows
        ],
        "by_decision": by_decision,
        "by_ticker_decision": by_ticker_decision,
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Before target trades | After target trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {bt} | {at} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                bt=len(payload["before_target_trades_by_window"][label]),
                at=len(payload["after_target_trades_by_window"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core-Misfit Trend Long No-Entry Shadow",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: post-sizing shares become zero only for `trend_long` signals in the current CORE_MISFIT_PAPER ticker set.",
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
            "No shared production policy, run adapter, backtester adapter, watchlist, or order path changed. Promotion would require a shared rule plus parity coverage.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def build_payload() -> dict[str, Any]:
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")
    coverage = _snapshot_coverage(list(TARGET_TICKERS))
    if not coverage["passed"]:
        raise RuntimeError(f"Gate 2 OHLCV coverage failed: {coverage}")

    before_results: dict[str, dict[str, Any]] = {}
    after_results: dict[str, dict[str, Any]] = {}
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_target_trades: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    after_target_trades: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    after_target_events: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    for label in WINDOWS:
        print(f"[{label}] baseline")
        before_results[label] = _run_window(label, haircut=False)
        print(f"[{label}] core-misfit trend_long no-entry")
        after_results[label] = _run_window(label, haircut=True)
        before_metrics[label] = base._metrics(before_results[label])
        after_metrics[label] = base._metrics(after_results[label])
        before_target_trades[label] = _target_trades(before_results[label])
        after_target_trades[label] = _target_trades(after_results[label])
        after_target_events[label] = _target_candidate_events(after_results[label])

    by_window_delta = OrderedDict(
        (label, base._delta(after_metrics[label], before_metrics[label]))
        for label in WINDOWS
    )
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._delta(aggregate_after, aggregate_before)
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
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in WINDOWS
    )
    before_trade_summary = _summarize_target_trades(before_target_trades)
    after_trade_summary = _summarize_target_trades(after_target_trades)
    after_event_summary = _summarize_candidate_events(after_target_events)
    no_share_count = int(after_event_summary["by_decision"].get("no_shares", 0))

    gate4_passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and len(regressed) <= 1
        and max_drawdown_worse <= 0.005
        and aggregate_after["min_survival_rate"] >= 0.05
        and before_trade_summary["trade_count"] >= 3
        and len(before_trade_summary["windows_with_trades"]) >= 2
        and no_share_count >= before_trade_summary["trade_count"]
    )
    decision = (
        "positive_replay_deferred_requires_shared_core_misfit_policy"
        if gate4_passed
        else "rejected_core_misfit_trend_long_no_entry"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The already-identified CORE_MISFIT_PAPER ticker set may be better "
            "handled as a no-entry long-risk governance sleeve for trend_long "
            "signals instead of waiting only for default-off inverse observation."
        ),
        "change_type": "long_risk_no_entry_shadow",
        "changed_variable": "core_misfit_trend_long_post_sizing_multiplier",
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260516-043",
            "exp-20260517-002",
            "exp-20260517-003",
            "exp-20260518-019",
            "exp-20260519-019",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "canonical_standard_snapshot_three_window_core_replay",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window core replay",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "parameters": {
            "target_tickers": list(TARGET_TICKERS),
            "target_strategy": TARGET_STRATEGY,
            "haircut_multiplier": HAIRCUT_MULTIPLIER,
            "locked_variables": [
                "universe",
                "signal rules",
                "ranking",
                "all non-target sizing rules",
                "exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": 2,
                "max_ev_regressed_windows": 1,
                "max_drawdown_worse": 0.005,
                "min_before_target_trades": 3,
                "min_before_target_windows": 2,
                "no_share_events_cover_before_target_trades": True,
            },
            "anti_js": "No JavaScript was used.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / no-trade alpha: existing core-misfit trend_long "
                "names should consume no new long risk until forward observation "
                "proves they are no longer a drag."
            ),
            "2_history_check": {
                "exp-20260516-043": (
                    "Accepted default-off CORE_MISFIT_PAPER observation scope "
                    "for TSM/ISRG/V/DDOG trend_long."
                ),
                "exp-20260517-003": (
                    "Fixed-10d inverse short made money but was too window-fragile "
                    "for live shorting."
                ),
                "exp-20260518-019": (
                    "trend_long conditioned short shadow was promising but "
                    "replay-only and not live-promotable."
                ),
                "exp-20260519-019": (
                    "Residual ticker expansion beyond TSM/ISRG/V/DDOG was rejected."
                ),
            },
            "3_single_causal_variable": (
                "post-sizing shares multiplier for TARGET_TICKERS when strategy == trend_long"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three-window before/after; accept only if "
                "aggregate EV/PnL improve, at least two windows improve, drawdown "
                "does not worsen by more than 0.5pp, survival stays >=5%, and "
                "the target cohort has enough pre-change trades across windows."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260523_011_core_misfit_trend_long_no_entry.py"
            ),
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
                "entry_candidate_events.ticker",
                "entry_candidate_events.strategy",
                "entry_candidate_events.decision",
                "signal.sizing.shares_to_buy",
                "target OHLCV rows in all three standard snapshots",
            ],
            "passed": gate2_open_positions["passed"] and coverage["passed"],
        },
        "gate3": {
            "new_filter_added": True,
            "minimum_after_survival_rate": aggregate_after["min_survival_rate"],
            "passed": aggregate_after["min_survival_rate"] >= 0.05,
            "note": (
                "The shadow rule sets post-sizing shares to zero; the backtester "
                "records these as no_shares entry decisions while signal survival "
                "is still audited."
            ),
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "max_drawdown_worse": base._round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": 0.005,
            "survival_guard_passed": aggregate_after["min_survival_rate"] >= 0.05,
            "before_target_trade_summary": before_trade_summary,
            "after_target_trade_summary": after_trade_summary,
            "after_target_candidate_event_summary": after_event_summary,
            "no_share_count": no_share_count,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "before_target_trades_by_window": before_target_trades,
        "after_target_trades_by_window": after_target_trades,
        "after_target_candidate_events_by_window": after_target_events,
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
            "live_short_enabled": False,
            "promotion_requirement": (
                "If accepted later, implement the no-entry rule in shared "
                "production/backtest policy with parity coverage before any live "
                "order behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking due sparse attribution; skipped new ticker "
            "pool expansion after BTC miner/HPC produced zero target trades; "
            "skipped event and state-surface near-neighbor scalar retunes due "
            "recent rejected trials and stricter repeat gates."
        ),
        "known_risks": [
            "The rule is a hard no-entry shadow and would require explicit shared production policy before promotion.",
            "The target cohort is already known from prior experiments, so multiple-testing risk is not zero.",
            "TSM and ISRG already have accepted partial core risk haircuts; this tests the remaining long-risk exposure after that stack.",
        ],
        "interpretation": (
            "The no-entry shadow improved the canonical replay and should be "
            "converted to a shared parity-tested policy before production use."
            if gate4_passed
            else (
                "Do not promote a CORE_MISFIT_PAPER trend_long no-entry rule. "
                "The replay did not clear the aggregate/window/risk/sample gate."
            )
        ),
        "rejection_reason": None
        if gate4_passed
        else (
            "CORE_MISFIT_PAPER trend_long no-entry failed Gate 4 on at least one "
            "required EV, PnL, window, drawdown, survival, or target-sample guard."
        ),
        "next_evidence_needed": (
            "Implement shared no-entry policy and parity tests, then rerun the "
            "same three windows before promotion."
            if gate4_passed
            else (
                "Keep the current default-off observation scope; reopen this "
                "long-risk no-entry idea only with forward closed outcomes or a "
                "new production-visible discriminator."
            )
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
            "title": "Core-misfit trend_long no-entry shadow",
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
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
