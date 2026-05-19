"""exp-20260509-014 state-surface benchmark momentum gate.

Alpha search, replay-only. Tests whether the state-surface satellite should
only participate when the broad index tape has positive recent momentum and the
core/event stack has enough local history to evaluate the sleeve.

Single causal variable:
    For the state-surface satellite only, require max(SPY, QQQ) trailing 20
    trading-day return > 0 after a 20-day core warm-up.

This does not change production orders, core A/B behavior, event source rules,
state-surface scoring, hold days, notional, LLM/news behavior, exits, sizing, or
live/default adapters. If promoted later, the gate must live in a shared adapter
used by run.py and backtester.py with parity tests.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260507_016_state_surface_satellite_replay as surface_base  # noqa: E402
from experiments import exp_20260507_026_non_generic_event_state_addon as event_base  # noqa: E402
from experiments import exp_20260509_012_event_state_plus_surface_stack as full_stack  # noqa: E402
from experiments.exp_20260504_034_form4_satellite_overlay import _delta  # noqa: E402


EXPERIMENT_ID = "exp-20260509-014"
STEM = "state_surface_benchmark_momentum_gate"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BEST_EVENT_VARIANT = full_stack.BEST_EVENT_VARIANT
LOOKBACK_DAYS = 20
BENCHMARK_TICKERS = ("SPY", "QQQ")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
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


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle_compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    needle_pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    kept = [
        line
        for line in lines
        if needle_compact not in line and needle_pretty not in line
    ]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _last_index_at_or_before(date_rows: list[dict[str, Any]], date_value: str) -> int | None:
    idx = None
    for row_idx, row in enumerate(date_rows):
        if str(row.get("date") or "") <= date_value:
            idx = row_idx
        else:
            break
    return idx


def _price_return(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
    lookback: int = LOOKBACK_DAYS,
) -> float | None:
    rows = prices.get(ticker) or []
    idx = _last_index_at_or_before(rows, date_value)
    if idx is None or idx - lookback < 0:
        return None
    start = rows[idx - lookback].get("close")
    end = rows[idx].get("close")
    if not start or not end:
        return None
    return float(end) / float(start) - 1.0


def _equity_return(
    result: dict[str, Any],
    date_value: str,
    lookback: int = LOOKBACK_DAYS,
) -> float | None:
    curve = list(result.get("equity_curve") or [])
    idx = None
    for row_idx, row in enumerate(curve):
        date = str(row[0] if isinstance(row, (list, tuple)) else row.get("date") or "")
        if date <= date_value:
            idx = row_idx
        else:
            break
    if idx is None or idx - lookback < 0:
        return None
    start_row = curve[idx - lookback]
    end_row = curve[idx]
    start_value = start_row[1] if isinstance(start_row, (list, tuple)) else start_row.get("equity")
    end_value = end_row[1] if isinstance(end_row, (list, tuple)) else end_row.get("equity")
    if not start_value or not end_value:
        return None
    return float(end_value) / float(start_value) - 1.0


def _gate_state(
    row: dict[str, Any],
    *,
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    decision_date = str(row.get("decision_date") or row.get("date") or "")[:10]
    core_return = _equity_return(result, decision_date)
    benchmark_returns = {
        ticker: _price_return(prices, ticker, decision_date)
        for ticker in BENCHMARK_TICKERS
    }
    ready_benchmark_returns = [
        value for value in benchmark_returns.values() if value is not None
    ]
    benchmark_return_max = max(ready_benchmark_returns) if ready_benchmark_returns else None
    allowed = (
        core_return is not None
        and benchmark_return_max is not None
        and benchmark_return_max > 0.0
    )
    return {
        "decision_date": decision_date,
        "core_trailing_return_20d": round(core_return, 6) if core_return is not None else None,
        "benchmark_returns_20d": {
            ticker: round(value, 6) if value is not None else None
            for ticker, value in benchmark_returns.items()
        },
        "benchmark_return_max_20d": (
            round(benchmark_return_max, 6) if benchmark_return_max is not None else None
        ),
        "core_warmup_ready": core_return is not None,
        "benchmark_momentum_positive": (
            benchmark_return_max is not None and benchmark_return_max > 0.0
        ),
        "allowed": allowed,
    }


def _filter_benchmark_momentum(
    candidates: list[dict[str, Any]],
    *,
    result: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept = []
    skipped = []
    for row in candidates:
        if row.get("status") != "price_ready":
            kept.append(row)
            continue
        gate = _gate_state(row, result=result, prices=prices)
        enriched = {**row, "benchmark_momentum_gate": gate}
        if gate["allowed"]:
            kept.append(enriched)
        else:
            skipped.append(
                {
                    **enriched,
                    "reason": "benchmark_momentum_gate_blocked",
                }
            )
    return kept, skipped


def _aggregate_delta(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_window = OrderedDict(
        (label, _delta(before[label], after[label])) for label in event_base.WINDOWS
    )
    baseline_ev = sum(float(before[label].get("expected_value_score") or 0.0) for label in event_base.WINDOWS)
    after_ev = sum(float(after[label].get("expected_value_score") or 0.0) for label in event_base.WINDOWS)
    baseline_pnl = sum(float(before[label].get("total_pnl") or 0.0) for label in event_base.WINDOWS)
    after_pnl = sum(float(after[label].get("total_pnl") or 0.0) for label in event_base.WINDOWS)
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 4),
        "after_ev_sum": round(after_ev, 4),
        "aggregate_ev_delta": round(after_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": round((after_ev - baseline_ev) / baseline_ev, 6) if baseline_ev else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "after_pnl_sum": round(after_pnl, 2),
        "aggregate_pnl_delta": round(after_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((after_pnl - baseline_pnl) / baseline_pnl, 6) if baseline_pnl else None,
        "windows_ev_improved": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("expected_value_score") or 0)
            > (before[label].get("expected_value_score") or 0)
        ),
        "windows_ev_regressed": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("expected_value_score") or 0)
            < (before[label].get("expected_value_score") or 0)
        ),
        "windows_pnl_improved": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("total_pnl") or 0) > (before[label].get("total_pnl") or 0)
        ),
        "windows_pnl_regressed": sum(
            1
            for label in event_base.WINDOWS
            if (after[label].get("total_pnl") or 0) < (before[label].get("total_pnl") or 0)
        ),
    }


def _single_ticker_positive_share(trades: list[dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    total_positive = 0.0
    for trade in trades:
        pnl = float(trade.get("pnl") or 0.0)
        if pnl <= 0:
            continue
        total_positive += pnl
        by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    if total_positive <= 0 or not by_ticker:
        return None
    return round(max(by_ticker.values()) / total_positive, 4)


def _selected_trade_rows(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        gate = trade.get("benchmark_momentum_gate") or {}
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "surface": trade.get("surface"),
                "decision_date": trade.get("decision_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "rank": trade.get("rank"),
                "score": trade.get("score"),
                "state_bucket": trade.get("state_bucket"),
                "breadth_bucket": trade.get("breadth_bucket"),
                "benchmark_return_max_20d": gate.get("benchmark_return_max_20d"),
                "core_trailing_return_20d": gate.get("core_trailing_return_20d"),
                "pnl": trade.get("pnl"),
                "net_return_pct": trade.get("net_return_pct"),
            }
        )
    return rows


def _surface_sleeve_summary(
    *,
    candidates: list[dict[str, Any]],
    full_selected: list[dict[str, Any]],
    gated_selected: list[dict[str, Any]],
    gate_skipped: list[dict[str, Any]],
    full_skipped: list[dict[str, Any]],
    gated_select_skipped: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "raw_candidate_count": len(candidates),
        "price_ready_candidate_count": sum(1 for row in candidates if row.get("status") == "price_ready"),
        "full_stack_selected_trade_count": len(full_selected),
        "benchmark_momentum_selected_trade_count": len(gated_selected),
        "benchmark_momentum_gate_skipped_price_ready_count": sum(
            1 for row in gate_skipped if row.get("status") == "price_ready"
        ),
        "full_stack_selected_pnl": round(sum(float(trade.get("pnl") or 0.0) for trade in full_selected), 2),
        "benchmark_momentum_selected_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in gated_selected),
            2,
        ),
        "full_stack_surface_summary": surface_base._surface_summary(full_selected),
        "benchmark_momentum_surface_summary": surface_base._surface_summary(gated_selected),
        "full_stack_selected_trades": _selected_trade_rows(full_selected),
        "benchmark_momentum_selected_trades": _selected_trade_rows(gated_selected),
        "skipped_reason_counts": dict(
            Counter(
                str(row.get("reason") or row.get("status") or "unknown")
                for row in [*gate_skipped, *gated_select_skipped, *full_skipped]
            )
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = event_base._load_event_trades()
    enriched_event_trades = event_base._enrich_event_trades(raw_event_trades)
    event_variant = event_base.VARIANTS[BEST_EVENT_VARIANT]

    event_state_metrics: dict[str, dict[str, Any]] = OrderedDict()
    full_stack_metrics: dict[str, dict[str, Any]] = OrderedDict()
    momentum_gate_metrics: dict[str, dict[str, Any]] = OrderedDict()
    surface_sleeve: dict[str, dict[str, Any]] = OrderedDict()
    all_momentum_trades: list[dict[str, Any]] = []

    for label, window in event_base.WINDOWS.items():
        result = event_base._load_core_result(window)
        event_trades = [
            event_base._scaled_trade(trade, BEST_EVENT_VARIANT, event_variant)
            for trade in enriched_event_trades[label]
        ]
        event_curve = event_base._event_equity_curve(
            event_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        event_state_metrics[label] = event_base._combined_metrics(result, event_curve, event_trades)

        candidates = surface_base._raw_candidates(
            label=label,
            window=window,
            result=result,
            prices=prices,
        )
        full_selected, full_skipped = surface_base._select_trades(candidates)
        full_stack_trades = event_trades + full_selected
        full_stack_curve = event_base._event_equity_curve(
            full_stack_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        full_stack_metrics[label] = event_base._combined_metrics(result, full_stack_curve, full_stack_trades)

        momentum_candidates, momentum_gate_skipped = _filter_benchmark_momentum(
            candidates,
            result=result,
            prices=prices,
        )
        momentum_selected, momentum_select_skipped = surface_base._select_trades(momentum_candidates)
        momentum_stack_trades = event_trades + momentum_selected
        momentum_stack_curve = event_base._event_equity_curve(
            momentum_stack_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        momentum_gate_metrics[label] = event_base._combined_metrics(
            result,
            momentum_stack_curve,
            momentum_stack_trades,
        )
        all_momentum_trades.extend({**trade, "window": label} for trade in momentum_selected)

        surface_sleeve[label] = _surface_sleeve_summary(
            candidates=candidates,
            full_selected=full_selected,
            gated_selected=momentum_selected,
            gate_skipped=momentum_gate_skipped,
            full_skipped=full_skipped,
            gated_select_skipped=momentum_select_skipped,
        )

    vs_event_state = _aggregate_delta(event_state_metrics, momentum_gate_metrics)
    vs_full_stack = _aggregate_delta(full_stack_metrics, momentum_gate_metrics)
    single_ticker_positive_share = _single_ticker_positive_share(all_momentum_trades)
    concentration_ok = single_ticker_positive_share is None or single_ticker_positive_share <= 0.50
    drawdown_cap_ok = all(
        float(momentum_gate_metrics[label].get("max_drawdown_pct") or 0.0) <= 0.20
        for label in event_base.WINDOWS
    )
    material_vs_event_state = (
        (vs_event_state["aggregate_ev_delta_pct"] or 0.0) > 0.10
        or (vs_event_state["aggregate_pnl_delta_pct"] or 0.0) > 0.05
    )
    aggregate_vs_full_positive = (
        vs_full_stack["aggregate_ev_delta"] > 0.0
        and vs_full_stack["aggregate_pnl_delta"] > 0.0
    )
    fixes_late_stack_risk = (
        vs_full_stack["by_window"]["late_strong"]["expected_value_score"] > 0.0
        and vs_full_stack["by_window"]["late_strong"]["sharpe_daily"] > 0.0
        and vs_full_stack["by_window"]["late_strong"]["max_drawdown_pct"] < 0.0
    )
    passed = bool(
        vs_event_state["windows_ev_improved"] == 3
        and material_vs_event_state
        and aggregate_vs_full_positive
        and fixes_late_stack_risk
        and drawdown_cap_ok
        and concentration_ok
    )

    if passed:
        decision = "promising_replay_only_benchmark_momentum_gate"
        decision_rationale = (
            "Promising replay-only lead: the benchmark-momentum gate improves all "
            "three windows versus the event-state add-on, improves aggregate EV "
            "and PnL versus the ungated exp-20260509-012 full stack, and fixes "
            "the late_strong stack risk flag. It is not a production/default "
            "promotion because mid_weak and old_thin still give back EV versus "
            "the ungated full stack."
        )
        rejection_reason = None
        next_action = (
            "Keep this as the strongest state-surface participation-gate paper "
            "candidate. Do not route orders until the gate is implemented in a "
            "shared run/backtester adapter with parity tests and forward closed "
            "trade evidence confirms the old_thin/mid_weak trade-off."
        )
    else:
        decision = "rejected"
        decision_rationale = (
            "Rejected: the benchmark-momentum gate did not clear the three-window "
            "event-state materiality, full-stack aggregate, late-risk, drawdown, "
            "and concentration guards."
        )
        rejection_reason = decision_rationale
        next_action = (
            "Do not promote or repeat this exact benchmark-momentum gate without "
            "new forward evidence or a different non-overfit discriminator."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "mechanism_family": "event_state_surface_stack_participation_gate",
        "alpha_hypothesis_category": "candidate_pool_allocation",
        "alpha_hypothesis": (
            "The state-surface satellite is most useful as a market-participation "
            "add-on when SPY/QQQ have positive 20-day momentum; requiring a "
            "20-day core warm-up should remove cold-start and negative-tape "
            "entries that caused late_strong stack risk."
        ),
        "hypothesis": (
            "Apply the frozen state-surface satellite only when max(SPY, QQQ) "
            "20-trading-day return is positive and the core/event stack has at "
            "least 20 local trading days of equity history."
        ),
        "change_type": "replay_only_state_surface_benchmark_momentum_gate",
        "single_causal_variable": (
            "benchmark-momentum participation gate on the frozen state-surface "
            "satellite; all scoring, sizing, hold, notional, and event-state "
            "settings remain locked"
        ),
        "parameters": {
            "event_variant": BEST_EVENT_VARIANT,
            "state_surface_policy": "frozen exp-20260509-010 mechanics",
            "lookback_trading_days": LOOKBACK_DAYS,
            "benchmarks": list(BENCHMARK_TICKERS),
            "gate": "core_warmup_ready and max(SPY_20d_return, QQQ_20d_return) > 0",
            "threshold_reason": "zero is the non-tuned positive/negative momentum boundary",
            "locked_variables": [
                "core A/B signal generation",
                "event source definitions",
                "event state add-on scalar",
                "state-surface scoring",
                "state-surface max candidates",
                "state-surface max active positions",
                "state-surface notional",
                "state-surface hold days",
                "LLM/news replay",
                "sizing",
                "exits",
                "universe",
            ],
        },
        "history_guardrails": {
            "checked_experiment_log": True,
            "checked_mechanism_insights": True,
            "not_repeated_failures": [
                "Not a surface allowlist, balanced-surface prune, or sector complement retry.",
                "Not a top-N, hold-day, notional, event-source, add-on heat, or state-score-floor retune.",
                "Not a ticker-level core-overlap exclusion from exp-20260509-011.",
                "Not an LLM soft-ranking or earnings/revisions experiment while those data remain sparse.",
            ],
            "why_this_is_not_a_simple_repeat": (
                "The gate uses only broad benchmark momentum and core warm-up "
                "availability. It does not inspect surface family, ticker, sector, "
                "event source, or future return, so it is orthogonal to the "
                "recently rejected same-sector, overlap, and surface-subset ideas."
            ),
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["snapshot"],
            }
            for label, window in event_base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in event_base.WINDOWS.items()
        },
        "before_metrics": {
            "event_state_addon": event_state_metrics,
            "full_stack_exp_20260509_012": full_stack_metrics,
        },
        "after_metrics": momentum_gate_metrics,
        "delta_metrics": {
            "vs_event_state_addon": vs_event_state,
            "vs_full_stack_exp_20260509_012": vs_full_stack,
        },
        "expected_value_score_delta": {
            "vs_event_state_addon": vs_event_state["aggregate_ev_delta"],
            "vs_full_stack_exp_20260509_012": vs_full_stack["aggregate_ev_delta"],
        },
        "gate4": {
            "passed": passed,
            "passed_vs_event_state_addon": (
                vs_event_state["windows_ev_improved"] == 3 and material_vs_event_state
            ),
            "aggregate_vs_full_stack_positive": aggregate_vs_full_positive,
            "fixes_late_stack_risk": fixes_late_stack_risk,
            "drawdown_cap_ok": drawdown_cap_ok,
            "concentration_ok": concentration_ok,
            "single_ticker_positive_share": single_ticker_positive_share,
            "primary_acceptance_rule": (
                "Require 3/3 EV improvement and material aggregate improvement "
                "versus event-state-only, positive aggregate EV/PnL versus the "
                "ungated full stack, late_strong EV/Sharpe/DD improvement versus "
                "the full stack, max drawdown <= 20%, and single-ticker positive "
                "share <= 50%."
            ),
        },
        "coverage": {
            "event_source_coverage": source_coverage,
            "event_trade_count": sum(
                int(event_base._trade_summary(enriched_event_trades[label])["trade_count"])
                for label in event_base.WINDOWS
            ),
            "surface_selected_trade_count": sum(
                int(surface_sleeve[label]["benchmark_momentum_selected_trade_count"])
                for label in event_base.WINDOWS
            ),
        },
        "surface_sleeve": surface_sleeve,
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_change": (
                "LLM soft-ranking remains sample-limited; this alpha test uses "
                "fully replayable OHLCV benchmark momentum and core equity history."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement_if_positive": (
                "Implement the benchmark-momentum gate in a shared policy/adapter "
                "consumed by run.py and backtester.py, expose the blocked/allowed "
                "reason in daily JSON, and add parity tests before any live/default orders."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": rejection_reason,
        "next_action": next_action,
        "risk_of_change": (
            "The gate can miss early-window positive state-surface trades and may "
            "underperform the ungated sleeve in older/weaker tapes where the "
            "state-surface signal finds leaders before the local stack has enough "
            "history."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking, earnings/revisions, event-source retunes, "
            "state-score floors, add-on heat reserve, sector complement, and "
            "surface subsets because recent logs mark them data-limited, rejected, "
            "or not the current marginal bottleneck."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-014 State-Surface Benchmark Momentum Gate",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Tests whether the state-surface satellite should participate only after a 20-day core warm-up and positive SPY/QQQ 20-day momentum.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Event-State EV | Full Stack EV | Momentum-Gated EV | vs Event EV | vs Full EV | vs Full PnL | vs Full Sharpe | vs Full DD | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in event_base.WINDOWS:
        event_metrics = payload["before_metrics"]["event_state_addon"][label]
        full_metrics = payload["before_metrics"]["full_stack_exp_20260509_012"][label]
        after = payload["after_metrics"][label]
        vs_event = payload["delta_metrics"]["vs_event_state_addon"]["by_window"][label]
        vs_full = payload["delta_metrics"]["vs_full_stack_exp_20260509_012"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {event_ev:.4f} | {full_ev:.4f} | {after_ev:.4f} | "
            "{vs_event_ev:+.4f} | {vs_full_ev:+.4f} | ${vs_full_pnl:+,.2f} | "
            "{vs_full_sharpe:+.2f} | {vs_full_dd:+.2%} | {trades} |".format(
                label=label,
                event_ev=event_metrics["expected_value_score"],
                full_ev=full_metrics["expected_value_score"],
                after_ev=after["expected_value_score"],
                vs_event_ev=vs_event["expected_value_score"],
                vs_full_ev=vs_full["expected_value_score"],
                vs_full_pnl=vs_full["total_pnl"],
                vs_full_sharpe=vs_full["sharpe_daily"],
                vs_full_dd=vs_full["max_drawdown_pct"],
                trades=sleeve["benchmark_momentum_selected_trade_count"],
            )
        )
    vs_event = payload["delta_metrics"]["vs_event_state_addon"]
    vs_full = payload["delta_metrics"]["vs_full_stack_exp_20260509_012"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "- Versus event-state add-on: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_event["aggregate_ev_delta"],
                vs_event["aggregate_ev_delta_pct"] or 0.0,
                vs_event["aggregate_pnl_delta"],
                vs_event["aggregate_pnl_delta_pct"] or 0.0,
                vs_event["windows_ev_improved"],
                vs_event["windows_ev_regressed"],
            ),
            "- Versus full exp-20260509-012 stack: EV {:+.4f} ({:+.2%}), PnL ${:+,.2f} ({:+.2%}), EV windows {}/{}.".format(
                vs_full["aggregate_ev_delta"],
                vs_full["aggregate_ev_delta_pct"] or 0.0,
                vs_full["aggregate_pnl_delta"],
                vs_full["aggregate_pnl_delta_pct"] or 0.0,
                vs_full["windows_ev_improved"],
                vs_full["windows_ev_regressed"],
            ),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay-only. No live/default orders, core A/B behavior, event source rules, LLM/news behavior, sizing, exits, or adapters changed. A promoted version needs shared run.py/backtester.py policy plus parity tests.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface benchmark momentum gate",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    compact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "llm_metrics": payload["llm_metrics"],
        "production_impact": payload["production_impact"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "next_action": payload["next_action"],
        "risk_of_change": payload["risk_of_change"],
        "related_files": payload["related_files"],
    }
    _append_jsonl_dedup(EXPERIMENT_LOG, compact)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "vs_event_state_addon": payload["delta_metrics"]["vs_event_state_addon"],
                    "vs_full_stack_exp_20260509_012": payload["delta_metrics"][
                        "vs_full_stack_exp_20260509_012"
                    ],
                    "gate4": payload["gate4"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
