"""Experiment exp-20260531-030: accepted free-data cross-source consensus.

Replay-only scout. It admits a default-off paper candidate when at least two
previously accepted free-data paper sleeves selected the same ticker on the
same signal date.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.experiments import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402


EXPERIMENT_ID = "exp-20260531-030"
STEM = "accepted_free_data_cross_source_consensus"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_candidate_pool"
CHANGED_VARIABLE = "accepted_free_data_cross_source_consensus_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE

MIN_SOURCE_COUNT = 2
BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 7
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

SOURCE_FILES = {
    "FUNDAMENTAL_GROWTH_RS_PAPER": Path(
        "data/experiments/exp-20260528-017/fundamental_growth_rs_low_liability_support.json"
    ),
    "VOLUME_BREADTH_BREAKOUT_PAPER": Path(
        "data/experiments/exp-20260529-004/exp_20260529_004_vbb_cost_liquidity_support.json"
    ),
    "FINRA_IWM_CONFIRMED_PAPER": Path(
        "data/experiments/exp-20260530-007/exp_20260530_007_finra_iwm_same_ticker_cooldown_candidate_pool.json"
    ),
    "ALPHA_SCORE_MARKET_REGIME_PAPER": Path(
        "data/experiments/exp-20260531-021/exp_20260531_021_full_universe_alpha_score_market_regime_safe_notional.json"
    ),
}

SOURCE_EXPERIMENT_IDS = {
    "FUNDAMENTAL_GROWTH_RS_PAPER": "exp-20260528-017",
    "VOLUME_BREADTH_BREAKOUT_PAPER": "exp-20260529-004",
    "FINRA_IWM_CONFIRMED_PAPER": "exp-20260530-007",
    "ALPHA_SCORE_MARKET_REGIME_PAPER": "exp-20260531-021",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "parity_note": (
        "This experiment reads accepted frozen paper artifacts and does not alter "
        "production order generation. Promotion would require a shared live/backtest "
        "cross-source consensus adapter before enabling any order impact."
    ),
}

OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_base_module() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _row_date(row: dict[str, Any]) -> str | None:
    for key in ("date", "signal_date", "entry_date"):
        value = row.get(key)
        if value:
            return str(value)
    return None


def _target_rows_by_window(source_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows_by_window: dict[str, list[dict[str, Any]]] = {}
    explicit = source_payload.get("target_trades_by_window")
    if isinstance(explicit, dict):
        for label, rows in explicit.items():
            if isinstance(rows, list):
                rows_by_window[str(label)] = [row for row in rows if isinstance(row, dict)]
        return rows_by_window

    for result in source_payload.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        label = str(result.get("label") or result.get("window_label") or "")
        if not label:
            continue
        rows = result.get("target_trades") or result.get("paper_trades") or []
        if isinstance(rows, list):
            rows_by_window[label] = [row for row in rows if isinstance(row, dict)]
    return rows_by_window


def _source_row_summary(source_name: str, row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "date",
        "signal_date",
        "entry_date",
        "ticker",
        "paper_pnl",
        "pnl_usd",
        "return_pct",
        "alpha_score",
        "fundamental_growth_rs_score",
        "volume_breadth_breakout_score",
        "candidate_selection_score",
        "source_overlap_count",
        "support_count",
        "same_ticker_cooldown_days",
    )
    summary = {"source_name": source_name, "source_experiment_id": SOURCE_EXPERIMENT_IDS[source_name]}
    for key in keys:
        if key in row:
            summary[key] = row.get(key)
    return summary


def _source_rows_by_window() -> dict[str, dict[tuple[str, str], list[dict[str, Any]]]]:
    combined: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for source_name, rel_path in SOURCE_FILES.items():
        path = ROOT / rel_path
        payload = _load_json(path)
        for label, rows in _target_rows_by_window(payload).items():
            for row in rows:
                signal_date = _row_date(row)
                ticker = str(row.get("ticker") or "").upper()
                if not signal_date or not ticker:
                    continue
                combined[label][(signal_date, ticker)].append(_source_row_summary(source_name, row))
    return combined


def _extract_source_numeric(source_rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_as_float(row.get(key)) for row in source_rows]
    values = [value for value in values if value is not None]
    if not values:
        return None
    return max(values)


def _consensus_candidates_for_window(
    label: str,
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for (signal_date, ticker), source_rows in source_rows_by_window.get(label, {}).items():
        source_names = sorted({str(row["source_name"]) for row in source_rows})
        if len(source_names) < MIN_SOURCE_COUNT:
            continue
        candidates.append(
            {
                "date": signal_date,
                "ticker": ticker,
                "source_count": len(source_names),
                "source_names": source_names,
                "source_experiment_ids": {
                    source_name: SOURCE_EXPERIMENT_IDS[source_name] for source_name in source_names
                },
                "source_rows": sorted(source_rows, key=lambda row: str(row.get("source_name") or "")),
                "fundamental_growth_rs_score": _extract_source_numeric(
                    source_rows, "fundamental_growth_rs_score"
                ),
                "alpha_score": _extract_source_numeric(source_rows, "alpha_score"),
                "volume_breadth_breakout_score": _extract_source_numeric(
                    source_rows, "volume_breadth_breakout_score"
                ),
                "finra_candidate_selection_score": _extract_source_numeric(
                    source_rows, "candidate_selection_score"
                ),
                "source_agreement_rule": "same_date_ticker_selected_by_at_least_two_accepted_free_data_sleeves",
                "known_at": f"{signal_date}T21:00:00Z",
                "trade_enabled": False,
                "alters_orders": False,
                "rule_version": RULE_VERSION,
                "strategy": "paper_candidate_pool_default_off",
            }
        )
    return sorted(
        candidates,
        key=lambda row: (
            str(row["date"]),
            -int(row["source_count"]),
            "+".join(row["source_names"]),
            str(row["ticker"]),
        ),
    )


def _select_target_trades(
    snapshot: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str]] = set()
    selected_per_day: Counter[str] = Counter()
    last_admitted_by_ticker: dict[str, date] = {}
    rejection_counts: Counter[str] = Counter()

    for candidate in candidates:
        signal_date = str(candidate["date"])
        ticker = str(candidate["ticker"])
        key = (signal_date, ticker)
        if key in selected_keys:
            rejection_counts["duplicate_same_day_ticker"] += 1
            continue
        if selected_per_day[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            rejection_counts["daily_trade_cap"] += 1
            continue
        parsed_date = date.fromisoformat(signal_date)
        last_date = last_admitted_by_ticker.get(ticker)
        if last_date is not None and (parsed_date - last_date).days < SAME_TICKER_COOLDOWN_DAYS:
            rejection_counts["same_ticker_cooldown"] += 1
            continue

        trade = base._paper_trade_from_candidate(snapshot, candidate)
        if trade is None:
            rejection_counts["missing_ohlcv_or_invalid_exit"] += 1
            continue
        trade.update(
            {
                "paper_pnl": trade.get("pnl"),
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "hold_days": HOLD_DAYS,
                "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
                "source_count": candidate["source_count"],
                "source_names": candidate["source_names"],
                "source_experiment_ids": candidate["source_experiment_ids"],
                "source_rows": candidate["source_rows"],
                "source_agreement_rule": candidate["source_agreement_rule"],
                "known_at": candidate["known_at"],
                "trade_enabled": False,
                "alters_orders": False,
                "rule_version": RULE_VERSION,
                "strategy": "paper_candidate_pool_default_off",
            }
        )
        selected.append(trade)
        selected_keys.add(key)
        selected_per_day[signal_date] += 1
        last_admitted_by_ticker[ticker] = parsed_date

    diagnostics = {
        "raw_consensus_candidates": len(candidates),
        "selected_target_trades": len(selected),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "selected_trade_dates": sorted(selected_per_day),
        "source_combo_counts_selected": dict(
            sorted(
                Counter("+".join(trade["source_names"]) for trade in selected).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
    }
    return selected, diagnostics


def _load_baselines() -> dict[str, dict[str, Any]]:
    baselines: dict[str, dict[str, Any]] = {}
    universe = sorted(base.get_universe())
    for label, cfg in base.WINDOWS.items():
        result = base.shadow._run_baseline(universe, cfg)
        baselines[label] = {
            "result": result,
            "metrics": base.overlay_helper._metrics(result),
        }
    return baselines


def _run_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in base.WINDOWS.items():
        snapshot = base.shadow._load_snapshot(cfg["snapshot"])
        candidates = _consensus_candidates_for_window(label, source_rows_by_window)
        target_trades, target_diagnostics = _select_target_trades(snapshot, candidates)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = base._overlay_from_paper_trades(before_result, target_trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = base.overlay_helper._delta(after, before)
        comparison = {
            "expected_value_score_delta": raw_delta["expected_value_score"],
            "strategy_total_pnl_delta": raw_delta["total_pnl"],
            "total_pnl_delta": raw_delta["total_pnl"],
            "max_drawdown_delta": raw_delta["max_drawdown_pct"],
            "raw_delta": raw_delta,
        }
        result_payload = {
            "label": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "before": before,
            "after": after,
            "comparison": comparison,
            "target_trade_count": len(target_trades),
            "target_trade_pnl_usd": sum(float(row.get("pnl", 0.0)) for row in target_trades),
            "raw_consensus_candidate_count": len(candidates),
            "target_diagnostics": target_diagnostics,
        }
        results.append(result_payload)
        target_trades_by_window[label] = target_trades
    return results, target_trades_by_window


def _aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in results)
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in results)
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in results)
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in results)
    before_agg = {
        "expected_value_score": round(before_ev, 6),
        "total_pnl": round(before_pnl, 2),
        "strategy_total_pnl": round(before_pnl, 2),
    }
    after_agg = {
        "expected_value_score": round(after_ev, 6),
        "total_pnl": round(after_pnl, 2),
        "strategy_total_pnl": round(after_pnl, 2),
    }
    comparison = {
        "expected_value_score_delta": round(after_ev - before_ev, 6),
        "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
        if before_ev
        else None,
        "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
        "total_pnl_delta": round(after_pnl - before_pnl, 2),
        "strategy_total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
        if before_pnl
        else None,
    }
    return {
        "before": before_agg,
        "after": after_agg,
        "comparison": comparison,
    }


def _target_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    positive_total = sum(max(float(trade.get("pnl", 0.0)), 0.0) for trade in all_trades)
    by_ticker: dict[str, dict[str, Any]] = {}
    for trade in all_trades:
        ticker = str(trade.get("ticker") or "")
        bucket = by_ticker.setdefault(
            ticker,
            {"ticker": ticker, "trade_count": 0, "paper_pnl_usd": 0.0, "positive_pnl_usd": 0.0},
        )
        pnl = float(trade.get("pnl", 0.0))
        bucket["trade_count"] += 1
        bucket["paper_pnl_usd"] += pnl
        bucket["positive_pnl_usd"] += max(pnl, 0.0)

    ticker_rows = sorted(
        by_ticker.values(),
        key=lambda row: (-float(row["paper_pnl_usd"]), -int(row["trade_count"]), str(row["ticker"])),
    )
    for row in ticker_rows:
        row["positive_pnl_share"] = (
            float(row["positive_pnl_usd"]) / positive_total if positive_total > 0 else 0.0
        )

    max_positive_share = max((float(row["positive_pnl_share"]) for row in ticker_rows), default=0.0)
    positive_hhi = sum(float(row["positive_pnl_share"]) ** 2 for row in ticker_rows)
    return {
        "target_trade_count": len(all_trades),
        "target_trade_pnl_usd": sum(float(row.get("pnl", 0.0)) for row in all_trades),
        "positive_pnl_total_usd": positive_total,
        "max_single_positive_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
        "ticker_rows": ticker_rows,
        "trades_by_window": {label: len(rows) for label, rows in target_trades_by_window.items()},
        "pnl_by_window": {
            label: sum(float(row.get("pnl", 0.0)) for row in rows)
            for label, rows in target_trades_by_window.items()
        },
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(comparison.get("strategy_total_pnl_delta") or 0.0)
    max_drawdown_delta = max(float(row["comparison"].get("max_drawdown_delta") or 0.0) for row in results)
    ev_windows_improved = [
        row["label"] for row in results if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows_improved = [
        row["label"] for row in results if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_trade_count = int(target_summary["target_trade_count"])

    gates = {
        "aggregate_expected_value_positive": ev_delta > 0.0,
        "aggregate_pnl_positive": pnl_delta > 0.0,
        "all_windows_expected_value_improved": len(ev_windows_improved) == len(results),
        "all_windows_pnl_improved": len(pnl_windows_improved) == len(results),
        "target_trade_count_passed": target_trade_count >= MIN_TARGET_TRADES,
        "target_window_count_passed": sum(1 for row in results if int(row["target_trade_count"]) > 0) >= MIN_TARGET_WINDOWS,
        "drawdown_drift_passed": max_drawdown_delta <= MAX_DRAWDOWN_WORSE,
        "survival_floor_passed": min_survival_rate >= 0.05,
        "concentration_guard_passed": (
            float(target_summary["max_single_positive_share"]) <= MAX_SINGLE_POSITIVE_SHARE
            and float(target_summary["positive_pnl_hhi"]) <= MAX_POSITIVE_HHI
        ),
    }
    passed = all(gates.values())
    if passed:
        decision = "positive_replay_lead_not_promoted_requires_shared_cross_source_adapter"
        rationale = (
            "Canonical three-window replay improved aggregate EV and PnL across all windows. "
            "No production behavior changes were made; promotion is blocked until the "
            "cross-source consensus signal is rebuilt as a shared live/backtest adapter."
        )
    else:
        decision = "rejected_accepted_free_data_cross_source_consensus_candidate_pool"
        rationale = "One or more Gate 4 acceptance checks failed, so the alpha change is not retained."
    return {
        "decision": decision,
        "passed": passed,
        "rationale": rationale,
        "gates": gates,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": max_drawdown_delta,
        "min_survival_rate": min_survival_rate,
        "requires_parity_before_promotion": passed,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "A ticker selected on the same date by at least two accepted free-data paper sleeves "
            "should have better replacement value than any single sleeve because independent "
            "candidate-pool mechanisms are agreeing without using future PnL."
        ),
        "category": "entry",
        "playbook_alignment": (
            "Matches the current playbook preference for broad, free, production-visible, "
            "default-off candidate-pool scouts instead of LLM soft-ranking or state-surface retunes."
        ),
        "nearby_prior_experiments": [
            "exp-20260531-026",
            "exp-20260531-029",
            "exp-20260529-008",
            "exp-20260528-017",
            "exp-20260530-007",
            "exp-20260529-004",
        ],
        "prior_difference": (
            "exp-20260531-026 and exp-20260531-029 required alpha-score primary overlap. "
            "This tests source-agnostic same-date agreement across any two accepted free-data sleeves."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": MIN_TARGET_TRADES,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "max_drawdown_drift": MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
        },
        "reproducibility": (
            "All source artifact paths, canonical windows, rule constants, before/after metrics, "
            "target trades, and rejection diagnostics are persisted in this experiment artifact."
        ),
    }


def _window_table(results: list[dict[str, Any]]) -> str:
    rows = [
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        before = row["before"]
        after = row["after"]
        comp = row["comparison"]
        rows.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(before["expected_value_score"]),
                after_ev=float(after["expected_value_score"]),
                ev_delta=float(comp["expected_value_score_delta"]),
                pnl_delta=float(comp["strategy_total_pnl_delta"]),
                dd_delta=float(comp["max_drawdown_delta"]),
            )
        )
    return "\n".join(rows)


def _write_card(payload: dict[str, Any]) -> None:
    aggregate = payload["aggregate"]
    comparison = aggregate["comparison"]
    decision = payload["gate4"]["decision"]
    lines = [
        f"# {EXPERIMENT_ID} accepted free-data cross-source consensus",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{decision}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Source Artifacts",
            "",
        ]
    )
    for source_name, source_path in SOURCE_FILES.items():
        lines.append(f"- `{source_name}`: `{source_path.as_posix()}`")
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "observed_only"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = str(OUT_JSON).replace("\\", "/")
            item["log"] = str(LOG_JSON).replace("\\", "/")
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            break
    _write_json(REGISTRY_JSON, registry)


def _update_ticket(payload: dict[str, Any]) -> None:
    if TICKET_JSON.exists():
        ticket = _load_json(TICKET_JSON)
    else:
        ticket = {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "status": "observed_only",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
    }


def main() -> None:
    _configure_base_module()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = _source_rows_by_window()
    baselines = _load_baselines()
    results, target_trades_by_window = _run_windows(baselines, source_rows)
    aggregate = _aggregate_results(results)
    target_summary = _target_summary(target_trades_by_window)
    gate4 = _gate4_decision(aggregate, results, target_summary)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "preflight": _preflight_payload(),
        "source_files": {name: str(path).replace("\\", "/") for name, path in SOURCE_FILES.items()},
        "rule": {
            "rule_version": RULE_VERSION,
            "min_source_count": MIN_SOURCE_COUNT,
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "aggregate": aggregate,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "gate4": gate4,
    }

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    _write_json(LOG_JSON, _experiment_log_record(payload))
    _write_card(payload)
    _update_ticket(payload)
    _upsert_registry(payload)
    base._upsert_jsonl(EXPERIMENT_LOG, _experiment_log_record(payload))

    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": gate4["decision"], "aggregate": aggregate["comparison"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
