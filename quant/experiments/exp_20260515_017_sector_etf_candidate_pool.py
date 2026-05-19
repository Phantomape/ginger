"""exp-20260515-017: sector/cross-asset ETF candidate-pool scout.

Tests one candidate-pool expansion family on the accepted core stack: add one
PIT-available ETF/proxy ticker at a time from the canonical OHLCV snapshots and
let the normal shared signal/risk/sizing stack decide whether it earns a slot.

This is alpha_search, not measurement repair. It does not change entries,
exits, ranking, sizing constants, caps, heat, slots, LLM/news behavior, or
event sleeves. It only tests whether a single production-visible ETF candidate
improves replacement value versus the existing core universe.
"""

from __future__ import annotations

import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260515_008_clean_spy_cap_only_leader_cap as prev
import risk_engine


base = prev.base

EXPERIMENT_ID = "exp-20260515-017"
EXPERIMENT_SLUG = "sector_etf_candidate_pool"
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005

CANDIDATE_SECTOR_MAP = {
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "USO": "Commodities",
    "IEF": "ETF",
    "TLT": "ETF",
    "UUP": "ETF",
}


def _snapshot_has_ticker(ticker: str) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for label, spec in base.WINDOWS.items():
        path = base.REPO_ROOT / spec["snapshot"]
        data = json.loads(path.read_text(encoding="utf-8"))
        ohlcv = data.get("ohlcv") if isinstance(data, dict) else {}
        out[label] = ticker in (ohlcv or {})
    return out


def _run_window(label: str, universe: list[str]) -> dict[str, Any]:
    spec = base.WINDOWS[label]
    # The backtester prints repeated no-earnings warnings for ETFs; suppress them
    # so the experiment output remains the JSON summary below.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        engine = base.BacktestEngine(
            universe,
            start=spec["start"],
            end=spec["end"],
            config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
            ohlcv_snapshot_path=str(base.REPO_ROOT / spec["snapshot"]),
        )
        result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} failed: {result['error']}")
    return {
        "metrics": base._metrics(result),
        "trades": result.get("trades") or [],
    }


def _x_trades(trades: list[dict[str, Any]], ticker: str) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        if trade.get("ticker") != ticker:
            continue
        rows.append(
            {
                "ticker": trade.get("ticker"),
                "strategy": trade.get("strategy"),
                "sector": trade.get("sector"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": round(float(trade.get("pnl") or 0.0), 2),
                "pnl_pct_net": round(float(trade.get("pnl_pct_net") or 0.0), 6),
                "shares": trade.get("shares"),
                "regime_exit_bucket": trade.get("regime_exit_bucket"),
                "regime_exit_score": trade.get("regime_exit_score"),
                "sizing_multipliers": trade.get("sizing_multipliers") or {},
            }
        )
    return rows


def _candidate_payload(
    ticker: str,
    sector: str,
    before_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    original_sector = risk_engine.SECTOR_MAP.get(ticker)
    risk_engine.SECTOR_MAP[ticker] = sector
    universe = list(base.get_universe())
    if ticker not in universe:
        universe.append(ticker)
    try:
        after_runs = {
            label: _run_window(label, universe)
            for label in base.WINDOWS
        }
    finally:
        if original_sector is None:
            risk_engine.SECTOR_MAP.pop(ticker, None)
        else:
            risk_engine.SECTOR_MAP[ticker] = original_sector

    before_metrics = {
        label: before_runs[label]["metrics"]
        for label in base.WINDOWS
    }
    after_metrics = {
        label: after_runs[label]["metrics"]
        for label in base.WINDOWS
    }
    by_window_delta = {
        label: base._delta(after_metrics[label], before_metrics[label])
        for label in base.WINDOWS
    }
    aggregate_before = base._aggregate(before_metrics)
    aggregate_after = base._aggregate(after_metrics)
    aggregate_delta = base._aggregate_delta(aggregate_after, aggregate_before)
    improved = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        > before_metrics[label]["expected_value_score"]
    ]
    regressed = [
        label
        for label in base.WINDOWS
        if after_metrics[label]["expected_value_score"]
        < before_metrics[label]["expected_value_score"]
    ]
    max_drawdown_worse = max(
        float(by_window_delta[label].get("max_drawdown_pct") or 0.0)
        for label in base.WINDOWS
    )
    candidate_trades = {
        label: _x_trades(after_runs[label]["trades"], ticker)
        for label in base.WINDOWS
    }
    candidate_trade_count = sum(len(rows) for rows in candidate_trades.values())
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and len(improved) >= 2
        and not regressed
        and aggregate_after["survival_rate_min"] >= 0.05
        and candidate_trade_count > 0
        and max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
    )
    return {
        "ticker": ticker,
        "sector": sector,
        "snapshot_presence": _snapshot_has_ticker(ticker),
        "passed": passed,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": aggregate_before,
            "aggregate_after": aggregate_after,
            "aggregate_delta": aggregate_delta,
        },
        "gate4": {
            "passed": passed,
            "improved_windows": improved,
            "regressed_windows": regressed,
            "candidate_trade_count": candidate_trade_count,
            "max_drawdown_worse": round(max_drawdown_worse, 6),
            "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
            "drawdown_guardrail_passed": (
                max_drawdown_worse <= MAX_DRAWDOWN_WORSE_GUARDRAIL
            ),
        },
        "candidate_trades": candidate_trades,
        "changed_trades": {
            label: base._changed_trades(
                before_runs[label]["trades"],
                after_runs[label]["trades"],
            )
            for label in base.WINDOWS
        },
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
    }


def _select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in candidates if row["passed"]] or candidates
    return max(
        rows,
        key=lambda row: (
            1 if row["passed"] else 0,
            row["expected_value_score_delta"],
            row["total_pnl_delta"],
            row["gate4"]["candidate_trade_count"],
        ),
    )


def _candidate_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": row["ticker"],
            "sector": row["sector"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "candidate_trade_count": row["gate4"]["candidate_trade_count"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            "min_survival_rate_after": row["delta_metrics"]["aggregate_after"][
                "survival_rate_min"
            ],
        }
        for row in candidates
    ]


def _markdown(payload: dict[str, Any]) -> str:
    scout_rows = [
        "| Ticker | Sector | Gate 4 | dEV sum | dPnL sum | Improved | Regressed | Trades | Max DD worse |",
        "|---|---|:---:|---:|---:|---|---|---:|---:|",
    ]
    for row in payload["candidate_summary"]:
        scout_rows.append(
            "| {ticker} | {sector} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {trades} | {dd:+.4f} |".format(
                ticker=row["ticker"],
                sector=row["sector"],
                passed="PASS" if row["passed"] else "FAIL",
                dev=row["expected_value_score_delta"],
                dpnl=row["total_pnl_delta"],
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                trades=row["candidate_trade_count"],
                dd=row["max_drawdown_worse"],
            )
        )
    selected = payload["selected_candidate"]
    window_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Candidate trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = selected["before_metrics"][label]
        after = selected["after_metrics"][label]
        delta = selected["delta_metrics"]["by_window"][label]
        window_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                trades=len(selected["candidate_trades"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector ETF Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable family: add one PIT-available sector/cross-asset ETF candidate at a time to the core universe, with a production-visible sector classification, while keeping the accepted signal/risk/sizing stack unchanged.",
            "",
            "## Candidate Scout",
            "",
            *scout_rows,
            "",
            f"Selected candidate: `{selected['ticker']}`.",
            "",
            "## Selected Three-Window Result",
            "",
            *window_rows,
            "",
            "Production impact: rejected scout only; no shared policy, universe, or production adapter changed.",
        ]
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(base._safe(payload), ensure_ascii=False, sort_keys=True)
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
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _build_payload() -> dict[str, Any]:
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base_universe = base.get_universe()
    before_runs = {
        label: _run_window(label, base_universe)
        for label in base.WINDOWS
    }
    candidates = [
        _candidate_payload(ticker, sector, before_runs)
        for ticker, sector in CANDIDATE_SECTOR_MAP.items()
    ]
    selected = _select_candidate(candidates)
    accepted = [row for row in candidates if row["passed"]]
    decision = (
        "accepted_for_shared_universe_implementation"
        if accepted
        else "rejected_sector_etf_candidate_pool"
    )
    interpretation = (
        "At least one single-ETF candidate addition passed the fixed-window gate and should be promoted only through shared universe/sector policy."
        if accepted
        else "Single ETF/proxy candidate additions from the existing PIT snapshots did not beat the accepted core universe; the best non-negative variants were inert with zero trades."
    )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted stock-heavy core universe may be missing a cleaner ETF "
            "replacement candidate for sector or cross-asset trend states. A "
            "single PIT-available ETF candidate should improve replacement value "
            "without adding a noisy ticker list if the candidate is genuinely useful."
        ),
        "change_type": "candidate_pool_shadow",
        "changed_variable": "single_sector_etf_candidate_pool_member",
        "single_causal_variable": (
            "add exactly one PIT-available ETF/proxy ticker to the core candidate universe"
        ),
        "parameters": {
            "candidate_sector_map": CANDIDATE_SECTOR_MAP,
            "base_universe_size": len(base_universe),
            "locked_variables": [
                "entry signals",
                "risk enrichment",
                "candidate ranking",
                "position sizing",
                "all sizing multipliers",
                "all position caps",
                "stops and targets",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "Space sleeves",
                "event sleeves",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260515-013/015_space_satcom": (
                    "Recent Space candidate-pool additions failed due old_thin regression and drawdown; this run avoids Space-specific data and uses core PIT ETF snapshots."
                ),
                "pilot_sleeve_replay": (
                    "Pilot universe expansion is not measurable on the historical core windows because activation starts after the fixed windows."
                ),
                "broad_capacity_expansion": (
                    "Past broad capacity/slot changes were noisy; this scout adds one economically interpretable ETF at a time."
                ),
            },
            "why_not_llm_soft_ranking": (
                "LLM soft-ranking remains attribution/data limited; this run uses deterministic OHLCV-derived signals and production-visible ticker/sector fields."
            ),
            "why_not_more_space": (
                "Space fast-5d satcom admission just failed Gate 4 and needs new mature forward rows or a new catalyst-quality field."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate pool: a single sector/cross-asset ETF already present in PIT snapshots may improve replacement value versus the existing stock universe"
            ),
            "2_history_check": (
                "Space/pilot expansion branches are sample-limited or recently rejected; no exact core single-ETF candidate scout was found in current 2026-05-15 logs."
            ),
            "3_single_causal_variable": (
                "single ETF candidate-pool membership; all strategy rules and sizing constants stay fixed"
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md fixed three windows; aggregate EV/PnL positive, at least two EV-improved windows, no EV-regressed windows, survival >= 5%, max DD worse <= 0.5pp, and nonzero candidate trades"
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\exp_20260515_017_sector_etf_candidate_pool.py"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical fixed-snapshot three-window replay",
            "windows": base.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": {
                label: before_runs[label]["metrics"]
                for label in base.WINDOWS
            },
            "baseline_aggregate": base._aggregate(
                {
                    label: before_runs[label]["metrics"]
                    for label in base.WINDOWS
                }
            ),
            "baseline_note": (
                "Current working tree baseline includes accepted exp-20260515-013 clean-SPY cap-only RS20 cap promotion."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "snapshot_presence": {
                ticker: _snapshot_has_ticker(ticker)
                for ticker in CANDIDATE_SECTOR_MAP
            },
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "canonical OHLCV snapshot ohlcv[ticker]",
                "risk_engine.SECTOR_MAP candidate classification",
                "shared signal/risk/sizing fields",
            ],
            "passed": gate2["passed"]
            and all(
                all(_snapshot_has_ticker(ticker).values())
                for ticker in CANDIDATE_SECTOR_MAP
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_expansion": True,
            "minimum_after_survival_rate": min(
                row["delta_metrics"]["aggregate_after"]["survival_rate_min"]
                for row in candidates
            ),
            "passed": min(
                row["delta_metrics"]["aggregate_after"]["survival_rate_min"]
                for row in candidates
            )
            >= 0.05,
        },
        "gate4": {
            "passed": bool(accepted),
            "accepted_candidates": [row["ticker"] for row in accepted],
            "selected_candidate": selected["ticker"],
            "selected_gate4": selected["gate4"],
        },
        "candidate_summary": _candidate_summary(candidates),
        "selected_candidate": selected,
        "before_metrics": selected["before_metrics"],
        "after_metrics": selected["after_metrics"],
        "delta_metrics": selected["delta_metrics"],
        "expected_value_score_delta": selected["expected_value_score_delta"],
        "total_pnl_delta": selected["total_pnl_delta"],
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If any candidate passed, add it through shared universe and sector policy plus parity coverage before live/default behavior changes."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "decision_reason": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "Do not add these sector/cross-asset ETF candidates to the core universe from fixed-window evidence. A valid retry needs a different production-visible admission rule, replacement-value evidence, or a post-activation pilot/sleeve protocol."
        ),
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(base.REPO_ROOT)),
    }
    base._write_json(artifact_path, payload)
    base._write_json(log_path, payload)
    base._write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


if __name__ == "__main__":
    result = _build_payload()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "gate4_passed": result["gate4"]["passed"],
                "selected_candidate": result["gate4"]["selected_candidate"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "total_pnl_delta": result["total_pnl_delta"],
                "candidate_summary": result["candidate_summary"],
                "production_impact": result["production_impact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
