"""exp-20260526-018: read-only VBB rank monotonic attribution."""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (
    REPO_ROOT / "quant",
    REPO_ROOT / "quant" / "experiments",
    REPO_ROOT / "quant" / "experiments" / "legacy",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_volatility_contraction_breakout_shadow as ohlcv_helper  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260526_013_volume_breadth_breakout_sleeve as vbb_source  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260526-018"
STEM = "vbb_rank_monotonic_attribution"
TRIAL_FAMILY = "volume_breadth_breakout_rank_monotonic_attribution"
CHANGED_VARIABLE = "vbb_volume_breadth_score_daily_rank_monotonicity_v1"
BASE_NOTIONAL_USD = 10_000.0
HOLD_DAYS = 10
MIN_BUCKET_TRADES = 8

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


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


def _paper_trade(snapshot: dict[str, list[dict[str, Any]]], row: dict[str, Any]) -> dict[str, Any] | None:
    rows = ohlcv_helper._series(snapshot, str(row.get("ticker") or ""))
    idx = ohlcv_helper._row_index(rows).get(str(row.get("date") or ""))
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = ohlcv_helper._value(rows[entry_idx], "Open")
    exit_raw = ohlcv_helper._value(rows[exit_idx], "Close")
    if not entry_raw or not exit_raw:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    return {
        **row,
        "signal_date": row.get("date"),
        "entry_date": ohlcv_helper._date(rows[entry_idx]),
        "exit_date": ohlcv_helper._date(rows[exit_idx]),
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(BASE_NOTIONAL_USD * pnl_pct_net, 2),
    }


def _rank_bucket(rank: int) -> str:
    if rank == 1:
        return "rank_1"
    if rank == 2:
        return "rank_2"
    return "rank_3_plus"


def _ranked_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        if row.get("same_ticker_ab_overlap"):
            rejected.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        by_date[str(row.get("date") or "")].append(row)

    trades: list[dict[str, Any]] = []
    for rows in by_date.values():
        ranked = sorted(
            rows,
            key=lambda row: (
                -float(row.get("volume_breadth_score") or 0.0),
                -float(row.get("candidate_day_rs_vs_spy") or 0.0),
                -float(row.get("volume_ratio_20") or 0.0),
                -float(row.get("dollar_volume") or 0.0),
                str(row.get("ticker") or ""),
            ),
        )
        for rank, row in enumerate(ranked, start=1):
            trade = _paper_trade(snapshot, row)
            if trade is None:
                rejected.append({**row, "filter_reason": "missing_next_open_or_exit"})
                continue
            trade["volume_breadth_candidate_rank_on_signal_date"] = rank
            trade["rank_bucket"] = _rank_bucket(rank)
            trade["daily_candidate_count"] = len(ranked)
            trades.append(trade)
    return trades, rejected


def _bucket_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "trade_count": 0,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "avg_return_pct": None,
            "median_return_pct": None,
            "win_rate": None,
            "positive_ticker_share_max": None,
        }
    returns = [float(row.get("pnl_pct_net") or 0.0) for row in rows]
    pnls = [float(row.get("pnl") or 0.0) for row in rows]
    by_ticker: Counter[str] = Counter()
    for row in rows:
        pnl = float(row.get("pnl") or 0.0)
        if pnl > 0:
            by_ticker[str(row.get("ticker") or "").upper()] += pnl
    positive_total = sum(by_ticker.values())
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2),
        "avg_return_pct": _round(sum(returns) / len(returns), 6),
        "median_return_pct": _round(median(returns), 6),
        "win_rate": _round(sum(1 for pnl in pnls if pnl > 0) / len(rows), 6),
        "positive_ticker_share_max": _round(max(by_ticker.values()) / positive_total, 6)
        if positive_total
        else None,
    }


def _bucket_summary(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary: dict[str, Any] = OrderedDict()
    all_rows: list[dict[str, Any]] = []
    for label, trades in trades_by_window.items():
        all_rows.extend(trades)
        summary[label] = OrderedDict(
            (bucket, _bucket_stats([row for row in trades if row.get("rank_bucket") == bucket]))
            for bucket in ("rank_1", "rank_2", "rank_3_plus")
        )
    summary["aggregate"] = OrderedDict(
        (bucket, _bucket_stats([row for row in all_rows if row.get("rank_bucket") == bucket]))
        for bucket in ("rank_1", "rank_2", "rank_3_plus")
    )
    return summary


def _is_monotonic(buckets: dict[str, dict[str, Any]]) -> bool:
    values = [buckets[b].get("avg_return_pct") for b in ("rank_1", "rank_2", "rank_3_plus")]
    counts = [int(buckets[b].get("trade_count") or 0) for b in ("rank_1", "rank_2", "rank_3_plus")]
    if any(value is None for value in values) or any(count < MIN_BUCKET_TRADES for count in counts):
        return False
    return float(values[0]) > float(values[1]) > float(values[2])


def _target_trade_summary(trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    by_window_pnl = {}
    for label, trades in trades_by_window.items():
        top_rows = [row for row in trades if row.get("rank_bucket") == "rank_1"]
        by_window_pnl[label] = round(sum(float(row.get("pnl") or 0.0) for row in top_rows), 2)
        for row in top_rows:
            ticker = str(row.get("ticker") or "").upper()
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += float(row.get("pnl") or 0.0)
    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [label for label, pnl in by_window_pnl.items() if pnl != 0.0],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_window_pnl": by_window_pnl,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())},
        "positive_by_ticker_pnl": {ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())},
        "max_single_positive_pnl_share": round(max(positive.values()) / positive_total, 6)
        if positive_total
        else None,
        "positive_pnl_hhi": round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total
        else None,
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    deltas: OrderedDict[str, dict[str, Any]] = OrderedDict()
    trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    rejected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    raw_candidate_counts: OrderedDict[str, int] = OrderedDict()
    candidate_day_counts: OrderedDict[str, int] = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay and VBB rank attribution")
        before_result = ohlcv_helper._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = ohlcv_helper._load_snapshot(cfg["snapshot"])
        candidates = vbb_source._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        ranked_trades, rejected = _ranked_trades(snapshot, candidates)
        rank1_trades = [row for row in ranked_trades if row.get("rank_bucket") == "rank_1"]
        overlay = base._overlay_from_paper_trades(before_result, rank1_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        before_metrics[label] = before
        after_metrics[label] = after
        deltas[label] = overlay_helper._delta(after, before)
        trades_by_window[label] = ranked_trades
        rejected_by_window[label] = rejected[:50]
        raw_candidate_counts[label] = len(candidates)
        candidate_day_counts[label] = len({row["date"] for row in candidates})

    bucket_summary = _bucket_summary(trades_by_window)
    monotonic_by_window = {label: _is_monotonic(bucket_summary[label]) for label in base.WINDOWS}
    aggregate_monotonic = _is_monotonic(bucket_summary["aggregate"])
    monotonic_window_count = sum(1 for value in monotonic_by_window.values() if value)
    decision = (
        "observed_only_vbb_rank_monotonic_positive"
        if aggregate_monotonic and monotonic_window_count == len(base.WINDOWS)
        else "rejected_vbb_rank_monotonicity_not_stable"
    )
    ev_delta_sum = _round(
        sum(row["expected_value_score"] for row in after_metrics.values())
        - sum(row["expected_value_score"] for row in before_metrics.values()),
        6,
    )
    pnl_delta_sum = _round(
        sum(row["total_pnl"] for row in after_metrics.values())
        - sum(row["total_pnl"] for row in before_metrics.values()),
        2,
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": "The accepted VBB sleeve should only be expanded or promoted if same-day score rank is monotonic across the three canonical windows.",
        "change_summary": "Read-only monotonic attribution of existing VBB score ranks.",
        "change_type": "read_only_rank_monotonic_attribution",
        "mechanism_family": "market_participation_quality_ranking",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 2,
        "nearby_prior_experiments": ["exp-20260526-013", "exp-20260526-014", "exp-20260526-017"],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "monotonic_validation_of_existing_production_visible_score",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "execution_model": "VBB signal uses signal-date OHLCV; paper entry is next open; exit is ten trading days later.",
        },
        "gate_questions": {
            "1_alpha_hypothesis": "ranking: existing VBB score rank should be monotonic before rank-depth or activation work.",
            "2_history_check": "exp-013 found top-1 replay-only VBB evidence; exp-014 shared default-off adapter; exp-017 rejected IWM gate. This does not retune breadth, breakout, volume, top-N, or notional.",
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": f"Require rank_1 avg return > rank_2 > rank_3_plus in aggregate and all 3 windows with each bucket count >= {MIN_BUCKET_TRADES}.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260526_018_vbb_rank_mono.py",
        },
        "gate1": {"baseline_metrics": before_metrics, "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics", "passed": True},
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Close/Volume rows",
                "SPY OHLCV rows for same-day relative strength",
                "volume_breadth_score from exp-20260526-013 VBB candidate source",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
            "note": "All ranking fields are production-visible in the shared default-off VBB paper adapter.",
        },
        "gate3": {"new_core_filter_added": False, "candidate_pool_changed": False, "passed": True, "note": "Read-only attribution; core survival and trade count are unchanged."},
        "gate4": {
            "passed": decision == "observed_only_vbb_rank_monotonic_positive",
            "aggregate_monotonic": aggregate_monotonic,
            "monotonic_by_window": monotonic_by_window,
            "monotonic_window_count": monotonic_window_count,
            "required_monotonic_windows": len(base.WINDOWS),
            "min_bucket_trades": MIN_BUCKET_TRADES,
            "top1_overlay_ev_delta_sum": ev_delta_sum,
            "top1_overlay_pnl_delta_sum": pnl_delta_sum,
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {"by_window": deltas, "aggregate": {"expected_value_score_delta_sum": ev_delta_sum, "total_pnl_delta_sum": pnl_delta_sum}},
        "rank_bucket_summary": bucket_summary,
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_day_counts": candidate_day_counts,
        "target_trade_summary": _target_trade_summary(trades_by_window),
        "sample_ranked_trades_by_window": OrderedDict((label, rows[:20]) for label, rows in trades_by_window.items()),
        "sample_rejected_candidates_by_window": rejected_by_window,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": "Future rank-depth or activation needs a separate Gate 1-4 shared-policy experiment.",
        },
        "rejection_reason": None if decision == "observed_only_vbb_rank_monotonic_positive" else "Existing VBB score rank was not monotonically ordered in every canonical window.",
        "next_retry_requires": ["closed forward VBB replacement-value rows", "materially new production-visible score component", "no frozen-sample top-N/rank-depth/notional retune"],
        "related_files": [_repo_rel(Path(__file__)), _repo_rel(OUT_JSON), _repo_rel(LOG_JSON), _repo_rel(TICKET_JSON), _repo_rel(ARTIFACT_MD), _repo_rel(EXPERIMENT_LOG)],
        "anti_js": "No JavaScript was used.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Rank 1 avg ret | Rank 2 avg ret | Rank 3+ avg ret | Rank 1 n | Rank 2 n | Rank 3+ n | Monotonic |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in [*base.WINDOWS.keys(), "aggregate"]:
        buckets = payload["rank_bucket_summary"][label]
        rows.append(
            "| {label} | {r1} | {r2} | {r3} | {n1} | {n2} | {n3} | {mono} |".format(
                label=label,
                r1=buckets["rank_1"]["avg_return_pct"],
                r2=buckets["rank_2"]["avg_return_pct"],
                r3=buckets["rank_3_plus"]["avg_return_pct"],
                n1=buckets["rank_1"]["trade_count"],
                n2=buckets["rank_2"]["trade_count"],
                n3=buckets["rank_3_plus"]["trade_count"],
                mono=payload["gate4"]["aggregate_monotonic"] if label == "aggregate" else payload["gate4"]["monotonic_by_window"][label],
            )
        )
    overlay_rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        overlay_rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VBB Rank Monotonic Attribution",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: read-only monotonic validation of the existing VBB same-day score rank.",
            "",
            "## Rank Monotonicity",
            "",
            *rows,
            "",
            "## Top-1 Overlay Sanity Check",
            "",
            *overlay_rows,
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Read-only replay attribution. No shared policy, adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "VBB rank monotonic attribution",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["rejection_reason"] or "VBB score rank monotonicity passed read-only attribution.",
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "gate4": payload["gate4"],
                    "rank_bucket_summary": payload["rank_bucket_summary"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
