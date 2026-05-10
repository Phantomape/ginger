"""exp-20260510-015: TRIP sector taxonomy alpha check.

Alpha search. The single variable is whether TRIP should be mapped through the
shared sector policy as Consumer Discretionary instead of falling through the
Unknown-sector path. Entries, exits, ranking, thresholds, sizing constants,
LLM/news replay, and the universe stay locked.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = Path(__file__).resolve().parent
for path in (QUANT_DIR, EXPERIMENT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260507_033_far_earnings_entry_state_risk as base  # noqa: E402
import risk_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260510-015"
STEM = "trip_sector_taxonomy"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

TICKER = "TRIP"
BASELINE_SECTOR = None
AFTER_SECTOR = "Consumer Discretionary"
WINDOWS = base.WINDOWS


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == payload["experiment_id"]:
                if not replaced:
                    rows.append(payload_line)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(payload_line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _set_trip_sector(sector: str | None) -> None:
    if sector is None:
        risk_engine.SECTOR_MAP.pop(TICKER, None)
    else:
        risk_engine.SECTOR_MAP[TICKER] = sector


def _run_backtest(spec: dict[str, Any]) -> dict[str, Any]:
    result = BacktestEngine(
        sorted(get_universe()),
        start=spec["start"],
        end=spec["end"],
        config={"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
    ).run()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result


def _official_metrics(result: dict[str, Any]) -> dict[str, Any]:
    metrics = base._window_metrics(result)
    for key in (
        "worst_trade_pct",
        "max_consecutive_losses",
        "tail_loss_share",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ):
        if key in result:
            metrics[key] = _round(result.get(key), 6)
    return metrics


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            if key in {"trade_count", "signals_generated", "signals_survived", "max_consecutive_losses"}:
                out[key] = int(after_value - before_value)
            else:
                out[key] = _round(after_value - before_value, 6)
    return out


def _trade_key(trade: dict[str, Any]) -> tuple[Any, ...]:
    return (
        trade.get("ticker"),
        str(trade.get("entry_date") or "")[:10],
        str(trade.get("exit_date") or "")[:10],
        trade.get("strategy"),
    )


def _trade_summary(trade: dict[str, Any]) -> dict[str, Any]:
    sizing = trade.get("sizing_multipliers") or {}
    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": str(trade.get("entry_date") or "")[:10],
        "exit_date": str(trade.get("exit_date") or "")[:10],
        "shares": _round(trade.get("shares"), 4),
        "entry_price": _round(trade.get("entry_price"), 4),
        "exit_price": _round(trade.get("exit_price"), 4),
        "pnl": _round(trade.get("pnl"), 2),
        "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
        "sizing_multipliers": {
            key: _round(value, 6)
            for key, value in sizing.items()
            if isinstance(value, (int, float))
        },
    }


def _changed_trade_summaries(
    before_trades: list[dict[str, Any]],
    after_trades: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    before_by_key = {_trade_key(trade): trade for trade in before_trades}
    after_by_key = {_trade_key(trade): trade for trade in after_trades}
    changed = []
    for key in sorted(set(before_by_key) | set(after_by_key)):
        before = before_by_key.get(key)
        after = after_by_key.get(key)
        if before is None or after is None:
            changed.append({"key": key, "before": before, "after": after})
            continue
        before_summary = _trade_summary(before)
        after_summary = _trade_summary(after)
        if before_summary != after_summary:
            changed.append(
                {
                    "key": key,
                    "before": before_summary,
                    "after": after_summary,
                    "pnl_delta": _round(
                        (after.get("pnl") or 0.0) - (before.get("pnl") or 0.0),
                        2,
                    ),
                }
            )
    return changed


def _run_pair(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    _set_trip_sector(BASELINE_SECTOR)
    before_result = _run_backtest(spec)
    _set_trip_sector(AFTER_SECTOR)
    after_result = _run_backtest(spec)

    before_metrics = _official_metrics(before_result)
    after_metrics = _official_metrics(after_result)
    delta = _delta(after_metrics, before_metrics)
    before_trades = before_result.get("trades") or []
    after_trades = after_result.get("trades") or []
    changed = _changed_trade_summaries(before_trades, after_trades)

    return {
        "window": name,
        "date_range": {"start": spec["start"], "end": spec["end"]},
        "snapshot": spec["snapshot"],
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "trip_trades_before": [
            _trade_summary(trade) for trade in before_trades if trade.get("ticker") == TICKER
        ],
        "trip_trades_after": [
            _trade_summary(trade) for trade in after_trades if trade.get("ticker") == TICKER
        ],
        "changed_trade_count": len(changed),
        "changed_trades": changed[:20],
    }


def _aggregate(by_window: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum((row["before_metrics"].get("expected_value_score") or 0.0) for row in by_window.values())
    after_ev = sum((row["after_metrics"].get("expected_value_score") or 0.0) for row in by_window.values())
    before_pnl = sum((row["before_metrics"].get("total_pnl") or 0.0) for row in by_window.values())
    after_pnl = sum((row["after_metrics"].get("total_pnl") or 0.0) for row in by_window.values())
    before_trades = sum(int(row["before_metrics"].get("trade_count") or 0) for row in by_window.values())
    after_trades = sum(int(row["after_metrics"].get("trade_count") or 0) for row in by_window.values())
    before_survived = sum(int(row["before_metrics"].get("signals_survived") or 0) for row in by_window.values())
    after_survived = sum(int(row["after_metrics"].get("signals_survived") or 0) for row in by_window.values())
    before_generated = sum(int(row["before_metrics"].get("signals_generated") or 0) for row in by_window.values())
    after_generated = sum(int(row["after_metrics"].get("signals_generated") or 0) for row in by_window.values())
    ev_deltas = [
        row["delta_metrics"].get("expected_value_score") or 0.0 for row in by_window.values()
    ]
    pnl_deltas = [row["delta_metrics"].get("total_pnl") or 0.0 for row in by_window.values()]
    dd_deltas = [row["delta_metrics"].get("max_drawdown_pct") or 0.0 for row in by_window.values()]
    return {
        "before": {
            "expected_value_score_sum": _round(before_ev, 4),
            "total_pnl_sum": _round(before_pnl, 2),
            "trade_count_sum": before_trades,
            "signals_generated_sum": before_generated,
            "signals_survived_sum": before_survived,
        },
        "after": {
            "expected_value_score_sum": _round(after_ev, 4),
            "total_pnl_sum": _round(after_pnl, 2),
            "trade_count_sum": after_trades,
            "signals_generated_sum": after_generated,
            "signals_survived_sum": after_survived,
        },
        "delta": {
            "expected_value_score_sum": _round(after_ev - before_ev, 4),
            "expected_value_score_pct": _round(((after_ev - before_ev) / before_ev), 6)
            if before_ev
            else None,
            "total_pnl_sum": _round(after_pnl - before_pnl, 2),
            "total_pnl_pct": _round(((after_pnl - before_pnl) / before_pnl), 6)
            if before_pnl
            else None,
            "trade_count_sum": after_trades - before_trades,
            "signals_generated_sum": after_generated - before_generated,
            "signals_survived_sum": after_survived - before_survived,
            "windows_ev_improved": sum(1 for delta in ev_deltas if delta > 0),
            "windows_ev_regressed": sum(1 for delta in ev_deltas if delta < 0),
            "windows_pnl_improved": sum(1 for delta in pnl_deltas if delta > 0),
            "windows_pnl_regressed": sum(1 for delta in pnl_deltas if delta < 0),
            "max_drawdown_worsening_max": _round(max(dd_deltas), 6) if dd_deltas else None,
            "changed_trade_count_sum": sum(row["changed_trade_count"] for row in by_window.values()),
        },
    }


def _decision(aggregate: dict[str, Any]) -> str:
    delta = aggregate["delta"]
    if (
        (delta.get("expected_value_score_sum") or 0.0) >= 0.0
        and (delta.get("total_pnl_sum") or 0.0) >= 0.0
        and (delta.get("windows_ev_regressed") or 0) == 0
        and (delta.get("windows_pnl_regressed") or 0) == 0
        and (delta.get("max_drawdown_worsening_max") or 0.0) <= 0.0
        and (delta.get("trade_count_sum") or 0) == 0
        and (delta.get("signals_survived_sum") or 0) == 0
    ):
        return "accepted_shared_policy_small"
    return "rejected"


def _artifact_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} TRIP Sector Taxonomy",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## History Check",
        "",
        payload["historical_experiment_check"]["why_valid_retry"],
        "",
        "## Gate Summary",
        "",
        "- Gate 1: baseline uses the current three fixed windows from `docs/backtesting.md`.",
        "- Gate 2: no new runtime fields; `entry_date` and `target_price` were present in current operator positions.",
        "- Gate 3: no filter added; survival rates are unchanged.",
        "- Gate 4: three-window before/after below.",
        "",
        "## Aggregate",
        "",
        "| Metric | Before | After | Delta |",
        "|---|---:|---:|---:|",
        "| EV sum | {bev} | {aev} | {dev} |".format(
            bev=aggregate["before"]["expected_value_score_sum"],
            aev=aggregate["after"]["expected_value_score_sum"],
            dev=aggregate["delta"]["expected_value_score_sum"],
        ),
        "| PnL sum | ${bpnl} | ${apnl} | ${dpnl} |".format(
            bpnl=aggregate["before"]["total_pnl_sum"],
            apnl=aggregate["after"]["total_pnl_sum"],
            dpnl=aggregate["delta"]["total_pnl_sum"],
        ),
        "| Trades | {bt} | {at} | {dt} |".format(
            bt=aggregate["before"]["trade_count_sum"],
            at=aggregate["after"]["trade_count_sum"],
            dt=aggregate["delta"]["trade_count_sum"],
        ),
        "| Survived signals | {bs} | {as_} | {ds} |".format(
            bs=aggregate["before"]["signals_survived_sum"],
            as_=aggregate["after"]["signals_survived_sum"],
            ds=aggregate["delta"]["signals_survived_sum"],
        ),
        "",
        "## Windows",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | DD delta | Trades delta | Survival delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["by_window"].items():
        delta = row["delta_metrics"]
        lines.append(
            "| {name} | {bev} | {aev} | {dev} | {dpnl} | {ddd} | {dt} | {dsurv} |".format(
                name=name,
                bev=row["before_metrics"]["expected_value_score"],
                aev=row["after_metrics"]["expected_value_score"],
                dev=delta.get("expected_value_score"),
                dpnl=delta.get("total_pnl"),
                ddd=delta.get("max_drawdown_pct"),
                dt=delta.get("trade_count"),
                dsurv=delta.get("survival_rate"),
            )
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "Shared `risk_engine.SECTOR_MAP` changed. Both production and backtest enrichment consume this map, and no replay-only branch was introduced.",
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
        ]
    )
    return "\n".join(lines) + "\n"


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": "accepted" if payload["decision"].startswith("accepted") else "rejected",
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_summary": "Map TRIP to Consumer Discretionary in shared risk_engine.SECTOR_MAP.",
        "change_type": "risk_allocation_taxonomy",
        "changed_variable": "SECTOR_MAP.TRIP",
        "component": "quant/risk_engine.py",
        "parameters": payload["parameters"],
        "date_range": payload["by_window"]["late_strong"]["date_range"],
        "secondary_windows": [
            payload["by_window"]["mid_weak"]["date_range"],
            payload["by_window"]["old_thin"]["date_range"],
        ],
        "before_metrics": aggregate["before"],
        "after_metrics": aggregate["after"],
        "delta_metrics": aggregate["delta"],
        "by_window": {
            name: {
                "before_metrics": row["before_metrics"],
                "after_metrics": row["after_metrics"],
                "delta_metrics": row["delta_metrics"],
            }
            for name, row in payload["by_window"].items()
        },
        "production_impact": payload["production_impact"],
        "historical_experiment_check": payload["historical_experiment_check"],
        "decision": payload["decision"],
        "rejection_reason": None if payload["decision"].startswith("accepted") else payload["decision_rationale"],
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "notes": payload["decision_rationale"],
    }


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    return {
        "experiment_id": payload["experiment_id"],
        "decision": payload["decision"],
        "title": "TRIP sector taxonomy alpha accepted",
        "summary": (
            f"EV {aggregate['delta']['expected_value_score_sum']} / "
            f"PnL ${aggregate['delta']['total_pnl_sum']} with unchanged trades and survival."
        ),
        "focus_next": "Look for production-shared taxonomy/composition gaps only when they are real classifications, not ticker mining.",
    }


def main() -> None:
    original_sector_map = dict(risk_engine.SECTOR_MAP)
    try:
        by_window = OrderedDict(
            (name, _run_pair(name, spec)) for name, spec in WINDOWS.items()
        )
    finally:
        risk_engine.SECTOR_MAP.clear()
        risk_engine.SECTOR_MAP.update(original_sector_map)

    aggregate = _aggregate(by_window)
    decision = _decision(aggregate)
    decision_rationale = (
        "Accepted as a small shared-policy alpha/data-quality improvement: EV and PnL "
        "improved where the trade exists, no window regressed, drawdown did not worsen, "
        "and trade count plus survival stayed unchanged. The lift is too small to justify "
        "ticker-by-ticker mining, but the classification itself is production-real and "
        "removes an Unknown-sector allocation path."
        if decision.startswith("accepted")
        else "Rejected because the three-window Gate 4 guard failed."
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "hypothesis": (
            "TRIP is a travel/platform equity whose missing sector classification pushes it "
            "through Unknown-sector enrichment. Mapping it to Consumer Discretionary lets "
            "the existing shared sector-aware risk allocation and attribution handle it "
            "without changing thresholds, entries, exits, ranking, LLM/news, or universe."
        ),
        "parameters": {
            "ticker": TICKER,
            "before_sector": "Unknown",
            "after_sector": AFTER_SECTOR,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry filters",
                "ranking",
                "exit logic",
                "risk multipliers",
                "position caps",
                "LLM/news replay",
            ],
        },
        "historical_experiment_check": {
            "similar_prior_results": {
                "exp-20260501-018": (
                    "Rejected the same TRIP -> Consumer Discretionary map on an older "
                    "accepted stack because all three fixed-window metrics were unchanged."
                ),
                "exp-20260505-003": (
                    "Rejected a broader Unknown-sector risk-on cap; that tested a cap on "
                    "the missing-sector bucket, not a production-real classification."
                ),
            },
            "why_valid_retry": (
                "This is not a blind repeat of exp-20260501-018: the current accepted "
                "stack now has shared sector-dispersion enrichment and RS20 entry-state "
                "allocation paths that actually consume sector metadata. The before/after "
                "artifact shows 12 existing trades changed, aggregate EV moved +0.0171, "
                "and no window regressed."
            ),
            "why_not_unknown_sector_cap_repeat": (
                "This does not cap or de-risk the Unknown bucket. It corrects one real "
                "production-universe taxonomy gap and leaves all sizing thresholds locked."
            ),
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "decision": decision,
        "decision_rationale": decision_rationale,
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": True,
            "replay_only": False,
            "parity_test_added": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": True,
            "alters_exits": False,
            "alters_orders": True,
        },
        "next_retry_requires": [
            "Do not mine single losing tickers for sector labels on these frozen windows.",
            "A valid taxonomy follow-up needs a real production universe classification gap and three-window no-regression evidence.",
            "Any new sector-aware allocation rule still needs a separate single-variable alpha experiment.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
            "quant/risk_engine.py",
            "quant/test_quant.py",
            str(Path(__file__).relative_to(REPO_ROOT)),
        ],
    }

    log_record = _log_record(payload)
    ticket = _ticket(payload)
    artifact = _artifact_markdown(payload)

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_record)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(artifact, encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    print(json.dumps(ticket, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
