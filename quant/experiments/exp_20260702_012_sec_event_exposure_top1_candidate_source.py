"""exp-20260702-012: SEC corporate-event exposure top-1 source.

This alpha-search runner converts the observed-only exp-20260702-011 raw
event-exposure lead into the first deployable shape: one default-off paper
candidate per signal date, selected by a fixed ex-ante rank.

It intentionally does not wire run.py or live/default orders. If economics pass,
the result is still only a replay lead until a shared helper and daily snapshot
are promoted. If economics fail, no strategy logic remains.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT, SCRIPTS_ROOT):
    value = str(import_path)
    if value not in sys.path:
        sys.path.insert(0, value)

import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as fixed_sleeve  # noqa: E402
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
import exp_20260702_011_sec_corporate_event_exposure_forward_value as lead  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402
from quant.evaluator_gates import ExperimentGateThresholds  # noqa: E402
from quant.full_stack_candidate_pool import (  # noqa: E402
    ExecutionEnvelope,
    evaluate_gate4 as evaluate_full_stack_gate4,
    evaluate_live_readiness,
    full_stack_verdict,
)


EXPERIMENT_ID = "exp-20260702-012"
OWNER = "alpha-explore"
SLUG = "sec_event_exposure_top1_candidate_source"
RUNNER = f"quant/experiments/exp_20260702_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260702_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
SAME_TICKER_COOLDOWN_CALENDAR_DAYS = 10
MIN_SIGNAL_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MAX_PAPER_TRADES_PER_DAY = 1

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
}
ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
}

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_late_strong_20260604.json"
                ),
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_mid_weak_20260604.json"
                ),
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "baseline": (
                    "data/backtests/archive/20260604_ohlcv_warehouse_replay/"
                    "backtest_results_warehouse_snapshot_old_thin_20260604.json"
                ),
            },
        ),
    ]
)

HYPOTHESIS = (
    "candidate_pool/full-stack scout: a fixed SEC corporate-event propagation "
    "top-1/day default-off paper source that selects one listed exposure ticker "
    "per filing date by event-class priority, relation priority, liquidity, "
    "and deterministic tie-break may preserve the exp-20260702-011 observed "
    "replacement-value lead after next-open 10d execution and comparator checks."
)
CHANGE_TYPE = "candidate_pool_full_stack"
IMPLEMENTATION_MODE = "private_replay_scout_due_unvalidated_top1_shape"
MECHANISM_FAMILY = "production_visible_sec_corporate_event_propagation"
TRIAL_FAMILY = "sec_event_exposure_top1_candidate_source"
TRIAL_VARIANT_ID = "fresh_ipo_then_425_theme_then_sic_liquidity_rank_v1"
CHANGED_VARIABLE = "sec_corporate_event_exposure_top1_day_candidate_source_v1"
NEW_EVIDENCE_TYPE = "new_sec_form_index_entity_exposure_top1_gate_shape"
NEW_EVIDENCE_AXIS = (
    "New data source plus new gate shape: form-type-first SEC S-1/F-1/425 "
    "corporate-event stream joined to entity-to-listed exposure map, now "
    "compressed into the first fixed top-1/day deployable propagation candidate "
    "source; this is not the parked SEC FTD/FINRA observer and not a same-field "
    "SEC text phrase/field scan."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260702-008",
    "exp-20260702-009",
    "exp-20260702-011",
    "exp-20260630-017",
]
CAUSAL_COMPONENTS = [
    "fixed S-1/F-1/425 event stream",
    "fixed entity exposure map",
    "fixed top-1/day source rank",
    "next-open 10d default-off paper replay",
    "execution envelope disclosure",
    "full-stack verdict without live/order wiring",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260702-012/exp_20260702_012_sec_event_exposure_top1_candidate_source.json",
    "experiments/cards/exp-20260702-012.md",
    "experiments/manifests/exp-20260702-012.json",
    "experiments/tickets/exp-20260702-012.json",
    "experiments/logs/exp-20260702-012.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=BASE_NOTIONAL_USD,
    max_capital_pct=0.40,
    min_dollar_volume=MIN_AVG_DOLLAR_VOLUME_20D,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=10,
    order_semantics="next_open_after_sec_filed_date",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Top-1/day, fixed $4,000 paper notional, 10-trading-session hold, "
        "10-calendar-day same-ticker cooldown, min $10 price and $50M ADV20. "
        "No daily helper or live adapter is promoted in this runner."
    ),
)
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": True,
    "run_adapter_changed": False,
    "daily_collector_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "live_ready": False,
    "default_off_paper_only": True,
    "uses_sec_corporate_event_stream": True,
    "uses_entity_exposure_map": True,
    "uses_hot_warehouse_forward_settlement": True,
    "live_realism_evaluated": True,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "This is a replay scout for the unvalidated top-1/day compression shape. "
        "A positive result would require a shared helper, daily default-off "
        "snapshot, and parity test before accepted paper promotion."
    ),
}

DEFAULT_PREDICTION = {
    "success_probability": 0.32,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "selection_compression_loses_edge",
        "window_instability",
        "accepted_comparator_not_beaten",
        "concentration_failed",
        "price_coverage_missing",
    ],
    "confidence_reason": (
        "exp-20260702-011 found a genuine new SEC form-index plus entity-exposure "
        "propagation lead across all canonical windows, but compressing many "
        "exposure rows into one deployable top-1/day default-off candidate may "
        "lose the edge and prior relation/peer attempts were often noisy."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    return round(number, digits) if number is not None else None


def parse_iso_date(value: Any) -> date | None:
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = dict(DEFAULT_PREDICTION)
    value = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(value, dict):
        prediction.update(value)
    prediction.setdefault("recorded_at", utc_now())
    return prediction


def immutable_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro&immutable=1"


def load_hot_ohlcv(tickers: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({str(ticker).upper() for ticker in tickers if ticker})
    if not HOT_WAREHOUSE.exists():
        return {}, {"exists": False, "warehouse": repo_rel(HOT_WAREHOUSE)}
    prices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    con = sqlite3.connect(immutable_uri(HOT_WAREHOUSE), uri=True)
    try:
        quick = con.execute("pragma quick_check").fetchone()
        warehouse_range = con.execute(
            "select min(date), max(date), count(*), count(distinct ticker) from ohlcv"
        ).fetchone()
        for start in range(0, len(requested), 750):
            chunk = requested[start : start + 750]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, close, volume from ohlcv "
                f"where ticker in ({placeholders}) order by ticker, date"
            )
            for ticker, day, open_px, close_px, volume in con.execute(sql, chunk):
                open_f = safe_float(open_px)
                close_f = safe_float(close_px)
                volume_f = safe_float(volume)
                if open_f is None or close_f is None or open_f <= 0 or close_f <= 0:
                    continue
                prices[str(ticker).upper()].append(
                    {
                        "date": str(day),
                        "open": open_f,
                        "close": close_f,
                        "volume": volume_f or 0.0,
                    }
                )
    finally:
        con.close()
    missing = sorted(set(requested) - set(prices))
    return dict(prices), {
        "exists": True,
        "warehouse": repo_rel(HOT_WAREHOUSE),
        "immutable_read": True,
        "quick_check": quick[0] if quick else None,
        "requested_ticker_count": len(requested),
        "price_ticker_count": len(prices),
        "missing_requested_ticker_count": len(missing),
        "missing_requested_ticker_sample": missing[:25],
        "warehouse_min_date": warehouse_range[0] if warehouse_range else None,
        "warehouse_max_date": warehouse_range[1] if warehouse_range else None,
        "warehouse_row_count": warehouse_range[2] if warehouse_range else None,
        "warehouse_ticker_count": warehouse_range[3] if warehouse_range else None,
    }


def prior_liquidity(
    rows: list[dict[str, Any]],
    signal_date: str,
) -> dict[str, Any]:
    if not rows:
        return {"status": "missing_ticker_prices"}
    dates = [row["date"] for row in rows]
    idx = bisect.bisect_right(dates, signal_date)
    if idx <= 0:
        return {"status": "no_price_before_signal"}
    sample = rows[max(0, idx - 20) : idx]
    if not sample:
        return {"status": "no_liquidity_sample"}
    adv_values = [
        float(row.get("close") or 0.0) * float(row.get("volume") or 0.0)
        for row in sample
        if safe_float(row.get("close")) is not None
    ]
    if not adv_values:
        return {"status": "no_adv_values"}
    last = sample[-1]
    return {
        "status": "ok",
        "signal_close": round(float(last["close"]), 4),
        "avg_dollar_volume_20d": round(sum(adv_values) / len(adv_values), 2),
        "liquidity_sample_days": len(sample),
    }


def settle_candidate(
    row: dict[str, Any],
    prices: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper()
    signal_date = str(row.get("filed_date") or "")[:10]
    rows = prices.get(ticker) or []
    dates = [item["date"] for item in rows]
    entry_idx = bisect.bisect_right(dates, signal_date)
    if entry_idx >= len(rows):
        return None
    exit_idx = entry_idx + HOLD_DAYS - 1
    if exit_idx >= len(rows):
        return None
    entry = rows[entry_idx]
    exit_row = rows[exit_idx]
    entry_fill = apply_entry_fill(float(entry["open"]), notional=BASE_NOTIONAL_USD)
    exit_fill = apply_slippage(
        float(exit_row["close"]),
        SLIPPAGE_BPS_TARGET,
        "sell",
        notional=BASE_NOTIONAL_USD,
    )
    if entry_fill is None or exit_fill is None or entry_fill <= 0:
        return None
    pnl_pct_net = (exit_fill / entry_fill) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    return {
        **row,
        "date": signal_date,
        "signal_date": signal_date,
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_raw_open": round(float(entry["open"]), 4),
        "exit_raw_close": round(float(exit_row["close"]), 4),
        "entry_price": round(float(entry_fill), 4),
        "exit_price": round(float(exit_fill), 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": round(pnl_pct_net, 6),
        "pnl": round(pnl, 2),
        "trade_enabled": False,
        "target_price": None,
        "target_price_resolution": "not_applicable_fixed_10d_paper_source",
    }


def event_priority(row: dict[str, Any]) -> int:
    if row.get("event_class") == "ipo_registration":
        return 0
    if row.get("event_class") == "merger_communication":
        return 1
    return 9


def relation_priority(row: dict[str, Any]) -> int:
    if row.get("primary_relation_type") == "theme_peer":
        return 0
    if row.get("primary_relation_type") == "sic_peer":
        return 1
    return 9


def selection_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        event_priority(row),
        relation_priority(row),
        -float(row.get("avg_dollar_volume_20d") or 0.0),
        str(row.get("ticker") or ""),
        str(row.get("event_accession") or ""),
        str(row.get("primary_entity_cik") or ""),
    )


def _cooldown_blocked(
    selected_by_ticker: dict[str, date],
    ticker: str,
    signal_day: date,
) -> bool:
    prior = selected_by_ticker.get(ticker)
    if prior is None:
        return False
    return (signal_day - prior).days <= SAME_TICKER_COOLDOWN_CALENDAR_DAYS


def build_ranked_candidates() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    exposure_rows, control_rows, source_summary = lead.build_candidate_rows()
    tickers = {str(row.get("ticker") or "").upper() for row in exposure_rows}
    prices, price_metadata = load_hot_ohlcv(tickers)
    ranked: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    filter_counts: Counter[str] = Counter()

    for row in exposure_rows:
        signal_date = str(row.get("filed_date") or "")[:10]
        label = lead.window_label(signal_date)
        if label not in WINDOWS:
            filter_counts["outside_canonical_windows"] += 1
            continue
        ticker = str(row.get("ticker") or "").upper()
        liquidity = prior_liquidity(prices.get(ticker, []), signal_date)
        if liquidity.get("status") != "ok":
            filter_counts[str(liquidity.get("status") or "missing_liquidity")] += 1
            filtered.append({**row, "filtered_reason": liquidity.get("status")})
            continue
        signal_close = safe_float(liquidity.get("signal_close"))
        adv20 = safe_float(liquidity.get("avg_dollar_volume_20d"))
        if signal_close is None or signal_close < MIN_SIGNAL_PRICE:
            filter_counts["price_below_min"] += 1
            filtered.append({**row, **liquidity, "filtered_reason": "price_below_min"})
            continue
        if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
            filter_counts["adv20_below_min"] += 1
            filtered.append({**row, **liquidity, "filtered_reason": "adv20_below_min"})
            continue
        settled = settle_candidate({**row, **liquidity, "window": label}, prices)
        if settled is None:
            filter_counts["unsettled_or_missing_forward_prices"] += 1
            filtered.append(
                {**row, **liquidity, "filtered_reason": "unsettled_or_missing_forward_prices"}
            )
            continue
        settled["event_priority"] = event_priority(settled)
        settled["relation_priority"] = relation_priority(settled)
        settled["rank_rule"] = (
            "ipo_registration_before_425; theme_peer_before_sic_peer; "
            "highest_adv20; ticker; accession; cik"
        )
        ranked.append(settled)

    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ranked:
        by_date[str(row.get("signal_date"))].append(row)

    selected: list[dict[str, Any]] = []
    selected_by_ticker: dict[str, date] = {}
    cooldown_skips = 0
    for signal_date in sorted(by_date):
        signal_day = parse_iso_date(signal_date)
        if signal_day is None:
            continue
        for row in sorted(by_date[signal_date], key=selection_sort_key):
            ticker = str(row.get("ticker") or "")
            if _cooldown_blocked(selected_by_ticker, ticker, signal_day):
                cooldown_skips += 1
                continue
            row = dict(row)
            row["selected_rank_on_date"] = 1
            row["max_paper_trades_per_day"] = MAX_PAPER_TRADES_PER_DAY
            selected.append(row)
            selected_by_ticker[ticker] = signal_day
            break

    audit = {
        "source_summary": source_summary,
        "price_metadata": price_metadata,
        "raw_exposure_rows": len(exposure_rows),
        "raw_control_rows": len(control_rows),
        "ranked_settled_candidates": len(ranked),
        "selected_top1_rows": len(selected),
        "filtered_rows_sample": filtered[:25],
        "filter_counts": dict(sorted(filter_counts.items())),
        "cooldown_skips": cooldown_skips,
        "selection_config": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "same_ticker_cooldown_calendar_days": SAME_TICKER_COOLDOWN_CALENDAR_DAYS,
            "min_signal_price": MIN_SIGNAL_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "rank_rule": (
                "fresh S-1/F-1 IPO registration before 425 merger communication; "
                "theme_peer before sic_peer; highest 20d dollar volume; ticker/accession/cik"
            ),
        },
        "candidate_counts_by_window": dict(
            sorted(Counter(str(row.get("window") or "missing") for row in ranked).items())
        ),
        "selected_counts_by_window": dict(
            sorted(Counter(str(row.get("window") or "missing") for row in selected).items())
        ),
    }
    return selected, ranked, audit


def load_window_baseline(label: str) -> dict[str, Any]:
    path = REPO_ROOT / WINDOWS[label]["baseline"]
    payload = read_json(path, {})
    if not payload:
        raise FileNotFoundError(f"missing baseline artifact for {label}: {path}")
    return payload


def metrics_with_overlay_pnl(
    before: dict[str, Any],
    overlay_total_pnl: float,
) -> dict[str, Any]:
    """Apply a fixed-notional paper overlay when baseline has no equity curve.

    The 20260604 per-window baseline artifacts used by this repo preserve
    canonical summary metrics but not daily equity curves. We therefore add only
    the realized paper PnL to total PnL/return and hold Sharpe/drawdown constant.
    This is conservative for positive overlays and blocks any live/accepted
    claim until a shared helper produces full daily replay parity.
    """
    after = dict(before)
    pnl = float(before.get("total_pnl") or 0.0) + float(overlay_total_pnl or 0.0)
    ret = float(before.get("strategy_total_return_pct") or 0.0) + (
        float(overlay_total_pnl or 0.0) / 100_000.0
    )
    sharpe = safe_float(before.get("sharpe_daily"))
    after["total_pnl"] = round(pnl, 2)
    after["strategy_total_return_pct"] = round(ret, 6)
    after["sharpe_daily"] = round_or_none(sharpe, 4)
    after["expected_value_score"] = (
        round(ret * sharpe, 4) if sharpe is not None else None
    )
    after["overlay_metric_caveat"] = (
        "summary_metric_overlay_without_baseline_equity_curve; sharpe and "
        "drawdown held at baseline"
    )
    return after


def split_by_window(rows: list[dict[str, Any]]) -> "OrderedDict[str, list[dict[str, Any]]]":
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict((label, []) for label in WINDOWS)
    for row in rows:
        label = str(row.get("window") or "")
        if label in out:
            out[label].append(row)
    return out


def top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values() if float(value) > 0)
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    for name, comparator in (
        ("compression", ACCEPTED_COMPRESSION_COMPARATOR),
        ("distribution", ACCEPTED_DISTRIBUTION_COMPARATOR),
    ):
        if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= comparator[
            "expected_value_score_delta_sum"
        ]:
            failed.append(f"accepted_{name}_ev_not_beaten")
        if float(aggregate["total_pnl_delta_sum"] or 0.0) <= comparator[
            "total_pnl_delta_sum"
        ]:
            failed.append(f"accepted_{name}_pnl_not_beaten")
    if not PRODUCTION_IMPACT["daily_snapshot_exposed"]:
        failed.append("daily_snapshot_not_exposed_for_full_stack_contract")
    return {
        "passed": not failed,
        "decision": (
            "accepted_sec_event_exposure_top1_candidate_source"
            if not failed
            else "rejected_sec_event_exposure_top1_candidate_source"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            "top5_positive_pnl_share": top5_positive_share(target_summary),
        },
        "accepted_comparators": {
            "compression": ACCEPTED_COMPRESSION_COMPARATOR,
            "distribution": ACCEPTED_DISTRIBUTION_COMPARATOR,
        },
        "full_stack_contract": {
            "daily_snapshot_exposed": PRODUCTION_IMPACT["daily_snapshot_exposed"],
            "parity_test_added": False,
        },
    }


def full_stack_blocks(aggregate: dict[str, Any], target_summary: dict[str, Any]) -> dict[str, Any]:
    metrics = {
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "adjusted_trade_count": target_summary["total_trade_count"],
        "adjusted_windows": target_summary["windows_with_target_trades"],
        "adjusted_window_count": len(target_summary["windows_with_target_trades"]),
        "max_drawdown_worse_max": aggregate["max_drawdown_delta_max"],
        "single_ticker_positive_share": target_summary["max_single_positive_pnl_share"],
        "top_5_contribution_pct": top5_positive_share(target_summary),
        "hhi_concentration": target_summary["positive_pnl_hhi"],
        "avg_pnl_per_trade_delta": (
            aggregate["total_pnl_delta_sum"] / target_summary["total_trade_count"]
            if target_summary["total_trade_count"]
            else None
        ),
    }
    thresholds = ExperimentGateThresholds(require_tail_concentration_not_worse=False)
    return {
        "window_metrics": metrics,
        "gate4_strict_materiality": evaluate_full_stack_gate4(
            metrics,
            thresholds=thresholds,
            check_materiality=True,
        ),
        "gate4_canonical": evaluate_full_stack_gate4(
            metrics,
            thresholds=thresholds,
            check_materiality=False,
        ),
        "materiality_note": (
            "Strict materiality is recorded for transparency. For candidate "
            "sources, the binding materiality standard is beating accepted "
            "comparators after costs."
        ),
    }


def calibrate(prediction: dict[str, Any], accepted: bool, failures: list[str], aggregate: dict[str, Any]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if accepted else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    failure_text = " ".join(failures)
    mode_hits = [
        mode
        for mode in predicted_modes
        if (
            (mode == "selection_compression_loses_edge" and "aggregate_pnl_not_positive" in failures)
            or (mode == "window_instability" and "window_" in failure_text)
            or (mode == "accepted_comparator_not_beaten" and "comparator" in failure_text)
            or (mode == "concentration_failed" and "concentration" in failure_text)
            or (mode == "price_coverage_missing" and "sample" in failure_text)
        )
    ]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_gate4_passed": accepted,
        "actual_success": 1 if accepted else 0,
        "brier_score": round((probability - actual) ** 2, 6),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": failures,
        "predicted_failure_modes_hit": mode_hits,
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket if isinstance(ticket, dict) else {})
    selected, ranked, audit = build_ranked_candidates()
    selected_by_window = split_by_window(selected)
    ranked_by_window = split_by_window(ranked)

    fixed_sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    fixed_sleeve.STEM = SLUG
    fixed_sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD

    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label in WINDOWS:
        before_result = load_window_baseline(label)
        before = overlay_helper._metrics(before_result)
        overlay = fixed_sleeve._overlay_from_paper_trades(
            before_result,
            selected_by_window[label],
        )
        after = metrics_with_overlay_pnl(before, float(overlay["overlay_total_pnl"] or 0.0))
        delta = overlay_helper._delta(after, before)
        before_metrics[label] = before
        after_metrics[label] = after
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_by_window[label]),
            "raw_candidate_count": len(ranked_by_window[label]),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = fixed_sleeve._target_trade_summary(selected_by_window)
    g4 = gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    fs_blocks = full_stack_blocks(aggregate, target_summary)
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    verdict = full_stack_verdict(
        gate4=g4,
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    accepted = bool(g4["passed"] and verdict["verdict"] != "reject")
    if not accepted:
        verdict = {
            **verdict,
            "verdict": "reject",
            "gate4_passed": False,
            "next_step": (
                "Reject and do not retune this top-1/day propagation source on "
                "the same frozen rows. A retry needs a shared daily helper with "
                "fresh forward rows, PIT SIC-as-of-filing repair, or a genuinely "
                "new relation/economic data source."
            ),
        }

    status = "accepted_paper_pending_forward" if accepted else "rejected"
    decision = g4["decision"]
    why = (
        "The raw exp011 propagation lead did not survive compression into one "
        "deployable top-1/day default-off source under the fixed liquidity, "
        "ranking, cooldown, next-open, and 10d paper-execution envelope."
        if not accepted
        else "The fixed top-1/day propagation source preserved the raw exp011 lead."
    )
    forbidden = (
        "Do not tune the form set, include IPO amendments, change event-class "
        "priority, relation priority, liquidity thresholds, hold days, cooldown, "
        "notional, theme overlay, SIC peer cap, or response shape on these same "
        "rows."
    )
    next_evidence = (
        "A valid retry needs a shared helper plus daily default-off snapshot with "
        "fresh forward rows, PIT SIC-as-of-filing repair, or a materially new "
        "entity relation/economic data source."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": accepted,
        "full_stack_verdict": verdict["verdict"],
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibrate(prediction, accepted, g4["failed_reasons"], aggregate),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "novelty_gate": (
                    "experiment.py new required novelty and saturated-source "
                    "overrides because the tool fingerprinted this as sec_text_event; "
                    "the recorded axis is a new form-index event stream plus "
                    "entity-exposure top-1/day gate shape."
                ),
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One fixed source-selection bundle: fresh IPO before 425, "
                "theme_peer before sic_peer, highest ADV20, one row per date, "
                "10-day hold and 10-calendar-day same-ticker cooldown."
            ),
            "4_success_failure_standard": {
                "canonical_windows": list(WINDOWS),
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
                "accepted_comparators": [
                    ACCEPTED_COMPRESSION_COMPARATOR,
                    ACCEPTED_DISTRIBUTION_COMPARATOR,
                ],
            },
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "event_rows": repo_rel(lead.EVENT_ROWS),
            "entity_rows": repo_rel(lead.ENTITY_ROWS),
            "sic_index": repo_rel(lead.SIC_INDEX),
            "theme_overlay": repo_rel(lead.THEME_OVERLAY),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "selection_config": audit["selection_config"],
        },
        "selection_audit": audit,
        "target_trade_summary": target_summary,
        "target_trades_by_window": selected_by_window,
        "window_rows": window_rows,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": aggregate,
        "gate1": {
            "passed": True,
            "baseline_artifacts": {
                label: WINDOWS[label]["baseline"] for label in WINDOWS
            },
            "before_metrics": before_metrics,
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "event_accession",
                "filed_date",
                "event_class",
                "entity_exposure_map ticker",
                "entry_date",
                "target_price",
                "avg_dollar_volume_20d",
            ],
            "event_rows_exists": lead.EVENT_ROWS.exists(),
            "entity_exposure_map_exists": lead.ENTITY_ROWS.exists()
            and lead.SIC_INDEX.exists()
            and lead.THEME_OVERLAY.exists(),
            "target_price_scope": "not_applicable_fixed_10d_paper_source",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No core executable filter was added; this is additive default-off paper.",
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
        },
        "gate4": g4,
        "full_stack": {
            **fs_blocks,
            "verdict": verdict,
            "live_readiness": live_readiness,
            "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": forbidden,
            "new_evidence_required": next_evidence,
        },
        "next_retry_requires": [next_evidence],
        "rejection_reason": None if accepted else ";".join(g4["failed_reasons"]),
        "related_files": [
            RUNNER,
            repo_rel(lead.EVENT_ROWS),
            repo_rel(lead.ENTITY_ROWS),
            repo_rel(lead.SIC_INDEX),
            repo_rel(lead.THEME_OVERLAY),
            repo_rel(HOT_WAREHOUSE),
            repo_rel(BASELINE_RESULT),
            repo_rel(LOG_JSON),
            repo_rel(OUT_JSON),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [RUNNER_COMMAND],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
        "decision",
        "accepted",
        "accepted_alpha",
        "full_stack_verdict",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "selection_audit",
        "target_trade_summary",
        "window_rows",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "full_stack",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "rejection_reason",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | EV delta | PnL delta | Target trades | Ranked candidates |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, item in payload["window_rows"].items():
        rows.append(
            "| {label} | {ev:+.4f} | {pnl} | {trades} | {raw} |".format(
                label=label,
                ev=float(item["delta"].get("expected_value_score") or 0.0),
                pnl=money(item["delta"].get("total_pnl")),
                trades=item["target_trade_count"],
                raw=item["raw_candidate_count"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC event exposure top-1 candidate source",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Full-stack verdict: `{payload['full_stack_verdict']}`",
            "- Production orders changed: no",
            f"- Aggregate EV delta: `{payload['delta_metrics']['expected_value_score_delta_sum']}`",
            f"- Aggregate PnL delta: `{money(payload['delta_metrics']['total_pnl_delta_sum'])}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Window Summary",
            "",
            "\n".join(rows),
            "",
            "## Gate 4",
            "",
            f"- Passed: `{payload['gate4']['passed']}`",
            f"- Failed reasons: `{payload['gate4']['failed_reasons']}`",
            "",
            "## Reproduction",
            "",
            f"```powershell\n{RUNNER_COMMAND}\n```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        BASELINE_RESULT,
        lead.EVENT_ROWS,
        lead.ENTITY_ROWS,
        lead.SIC_INDEX,
        lead.THEME_OVERLAY,
        HOT_WAREHOUSE,
        REPO_ROOT / "experiments" / "logs" / "exp-20260702-011.json",
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, compact_log_record(payload))
    write_text(CARD_MD, build_card(payload))

    ticket_before = payload.get("ticket_before") or {}
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": payload["delta_metrics"][
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": payload["delta_metrics"][
            "total_pnl_delta_sum"
        ],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "full_stack_verdict": payload["full_stack_verdict"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "aggregate_ev_delta": payload["delta_metrics"][
                    "expected_value_score_delta_sum"
                ],
                "aggregate_pnl_delta": payload["delta_metrics"]["total_pnl_delta_sum"],
                "target_trade_count": payload["target_trade_summary"]["total_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
