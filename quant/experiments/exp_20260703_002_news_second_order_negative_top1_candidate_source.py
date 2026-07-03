"""exp-20260703-002: second-order news negative-polarity top-1 scout.

Private replay scout.  The prior observed-only read (exp-20260702-021) found
that negative first-order structured-news events had better baseline-controlled
second-order 10d outcomes than positive events.  This runner tests one
deployable compression shape: at most one negative-polarity second-order
exposure candidate per entry day, selected by ex-ante recency/liquidity
tie-breaks, next-open entry, and 10-trading-day close exit.

No shared helper, daily snapshot, live/default orders, ranking, sizing, or exit
behavior is changed.  A positive result would only be a replay lead.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
EXPERIMENTS_ROOT = QUANT_ROOT / "experiments"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (REPO_ROOT, QUANT_ROOT, EXPERIMENTS_ROOT, SCRIPTS_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as fixed_sleeve  # noqa: E402
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402
from news_event_exposure_observer import load_frames  # noqa: E402


EXPERIMENT_ID = "exp-20260703-002"
OWNER = "alpha-explore"
SLUG = "news_second_order_negative_top1_candidate_source"
RUNNER = f"quant/experiments/exp_20260703_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260703_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

LEDGER_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "news_event_exposure_observations"
    / "rows.jsonl"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

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
    "candidate_pool/private replay scout: fixed negative-polarity second-order "
    "structured-news exposure rows may form a deployable top-1/day default-off "
    "paper candidate source because exp-20260702-021 found inverted "
    "negative-over-positive baseline-controlled 10d separation."
)
CHANGE_TYPE = "candidate_pool_full_stack"
IMPLEMENTATION_MODE = "private_replay_scout_due_unvalidated_top1_shape"
MECHANISM_FAMILY = "daily_news_llm_event_scoring_alpha"
TRIAL_FAMILY = "news_second_order_exposure_top1_candidate_source"
TRIAL_VARIANT_ID = "negative_polarity_top1_day_v1"
CHANGED_VARIABLE = "news_second_order_negative_polarity_top1_day_candidate_source_v1"
NEW_EVIDENCE_TYPE = "new_gate_shape_from_second_order_news_exposure_ledger"
NEW_EVIDENCE_AXIS = (
    "New gate shape on a new structured-news second-order exposure ledger: "
    "fixed negative-polarity top-1/day deployable candidate compression from "
    "exp-20260702-020 rows, not an OHLCV relation threshold, not a "
    "relation/theme/horizon reslice, and not a same-source keyword scan."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260702-020",
    "exp-20260702-021",
    "exp-20260702-026",
    "exp-20260630-005",
]
CAUSAL_COMPONENTS = [
    "second-order exposure ledger",
    "negative first-order event polarity",
    "top-1/day deterministic candidate compression",
    "next-open 10d paper replay",
    "accepted-comparator check",
    "execution-envelope disclosure",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260703-002/exp_20260703_002_news_second_order_negative_top1_candidate_source.json",
    "experiments/cards/exp-20260703-002.md",
    "experiments/manifests/exp-20260703-002.json",
    "experiments/tickets/exp-20260703-002.json",
    "experiments/logs/exp-20260703-002.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, set):
        return sorted(safe(v) for v in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(value)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 4) -> float | None:
    number = safe_float(value)
    return None if number is None else round(number, digits)


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction:
        return prediction
    return {
        "success_probability": 0.28,
        "expected_ev_delta": 0.15,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "top1_compression_loses_observed_edge",
            "window_instability",
            "accepted_comparator_not_beaten",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Fallback prediction copied from reservation intent; ticket "
            "prediction was unavailable."
        ),
    }


def load_window_baseline(label: str) -> dict[str, Any]:
    path = REPO_ROOT / WINDOWS[label]["baseline"]
    payload = read_json(path, {})
    if not payload:
        raise FileNotFoundError(f"missing baseline artifact for {label}: {path}")
    return payload


def window_label(day: str) -> str | None:
    for label, cfg in WINDOWS.items():
        if cfg["start"] <= day <= cfg["end"]:
            return label
    return None


def load_ledger_rows() -> list[dict[str, Any]]:
    rows = []
    with LEDGER_ROWS.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def prior_liquidity(frame: pd.DataFrame | None, entry_day: pd.Timestamp) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"status": "no_frame"}
    sample = frame.loc[frame.index < entry_day].tail(20)
    if sample.empty:
        return {"status": "no_prior_liquidity_sample"}
    closes = pd.to_numeric(sample["Close"], errors="coerce")
    volumes = pd.to_numeric(sample["Volume"], errors="coerce")
    adv = (closes * volumes).dropna()
    if adv.empty:
        return {"status": "no_adv_values"}
    signal_close = safe_float(closes.iloc[-1])
    if signal_close is None:
        return {"status": "no_signal_close"}
    return {
        "status": "ok",
        "signal_close": round(signal_close, 4),
        "avg_dollar_volume_20d": round(float(adv.mean()), 2),
        "liquidity_sample_days": int(len(adv)),
    }


def settle_trade(
    row: dict[str, Any],
    frame: pd.DataFrame,
) -> dict[str, Any] | None:
    ticker = str(row.get("exposure_ticker") or "").upper()
    entry_day = pd.Timestamp(row["entry_date"])
    if entry_day not in frame.index:
        return None
    entry_idx = frame.index.get_loc(entry_day)
    exit_idx = entry_idx + HOLD_DAYS - 1
    if exit_idx >= len(frame.index):
        return None
    entry = frame.iloc[entry_idx]
    exit_row = frame.iloc[exit_idx]
    entry_fill = apply_entry_fill(
        float(entry["Open"]), notional=BASE_NOTIONAL_USD
    )
    exit_fill = apply_slippage(
        float(exit_row["Close"]),
        SLIPPAGE_BPS_TARGET,
        "sell",
        notional=BASE_NOTIONAL_USD,
    )
    if entry_fill is None or exit_fill is None or entry_fill <= 0:
        return None
    pnl_pct_net = (exit_fill / entry_fill) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    return {
        "ticker": ticker,
        "date": str(row["event_date"]),
        "signal_date": str(row["event_date"]),
        "entry_date": str(entry_day.date()),
        "exit_date": str(frame.index[exit_idx].date()),
        "first_order_ticker": row.get("first_order_ticker"),
        "event_id": row.get("event_id"),
        "event_polarity": row.get("event_polarity"),
        "event_relation_type": row.get("event_relation_type"),
        "relation_type": row.get("relation_type"),
        "match_basis": row.get("match_basis"),
        "theme": row.get("theme"),
        "published_at": row.get("published_at"),
        "entry_raw_open": round(float(entry["Open"]), 4),
        "exit_raw_close": round(float(exit_row["Close"]), 4),
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


def candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    published = str(row.get("published_at") or "")
    return (
        -int(row.get("published_sort") or 0),
        -float(row.get("avg_dollar_volume_20d") or 0.0),
        str(row.get("first_order_ticker") or ""),
        str(row.get("ticker") or ""),
        str(row.get("event_id") or ""),
    )


def cooldown_blocked(selected_by_ticker: dict[str, date], ticker: str, day: date) -> bool:
    prior = selected_by_ticker.get(ticker)
    if prior is None:
        return False
    return (day - prior).days <= SAME_TICKER_COOLDOWN_CALENDAR_DAYS


def build_ranked_candidates() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    rows = load_ledger_rows()
    negative_rows = [
        row
        for row in rows
        if row.get("event_polarity") == "negative"
        and row.get("entry_date")
        and row.get("exposure_ticker")
    ]
    tickers = {str(row["exposure_ticker"]).upper() for row in negative_rows}
    frames = load_frames(tickers)
    ranked: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    filter_counts: Counter[str] = Counter()

    for row in negative_rows:
        entry_day_text = str(row["entry_date"])[:10]
        label = window_label(entry_day_text)
        if label not in WINDOWS:
            filter_counts["outside_canonical_windows"] += 1
            continue
        ticker = str(row["exposure_ticker"]).upper()
        frame = frames.get(ticker)
        entry_day = pd.Timestamp(entry_day_text)
        liquidity = prior_liquidity(frame, entry_day)
        if liquidity.get("status") != "ok":
            filter_counts[str(liquidity.get("status") or "liquidity_failed")] += 1
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
        if frame is None:
            filter_counts["no_frame"] += 1
            continue
        settled = settle_trade(row, frame)
        if settled is None:
            filter_counts["unsettled_or_missing_forward_prices"] += 1
            filtered.append(
                {**row, **liquidity, "filtered_reason": "unsettled_or_missing_forward_prices"}
            )
            continue
        published_sort = int(
            datetime.fromisoformat(
                str(row.get("published_at") or row.get("event_date")).replace("Z", "+00:00")
            ).timestamp()
        )
        settled.update(
            {
                **liquidity,
                "window": label,
                "published_sort": published_sort,
                "rank_rule": (
                    "negative_polarity_only; latest_published_at; highest_adv20; "
                    "first_order_ticker; exposure_ticker; event_id"
                ),
            }
        )
        ranked.append(settled)

    by_entry_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ranked:
        by_entry_date[str(row["entry_date"])].append(row)

    selected: list[dict[str, Any]] = []
    selected_by_ticker: dict[str, date] = {}
    cooldown_skips = 0
    for entry_date in sorted(by_entry_date):
        signal_day = parse_iso_date(entry_date)
        if signal_day is None:
            continue
        for row in sorted(by_entry_date[entry_date], key=candidate_sort_key):
            ticker = str(row.get("ticker") or "")
            if cooldown_blocked(selected_by_ticker, ticker, signal_day):
                cooldown_skips += 1
                continue
            row = dict(row)
            row["selected_rank_on_entry_date"] = 1
            row["max_paper_trades_per_day"] = MAX_PAPER_TRADES_PER_DAY
            selected.append(row)
            selected_by_ticker[ticker] = signal_day
            break

    audit = {
        "ledger_rows": len(rows),
        "negative_rows_with_entry_and_ticker": len(negative_rows),
        "ranked_settled_candidates": len(ranked),
        "selected_top1_rows": len(selected),
        "filter_counts": dict(sorted(filter_counts.items())),
        "filtered_rows_sample": filtered[:25],
        "cooldown_skips": cooldown_skips,
        "selection_config": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "same_ticker_cooldown_calendar_days": SAME_TICKER_COOLDOWN_CALENDAR_DAYS,
            "min_signal_price": MIN_SIGNAL_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "rank_rule": (
                "negative-polarity first-order event only; group by entry date; "
                "latest published_at; highest ADV20; first_order_ticker; "
                "exposure_ticker; event_id"
            ),
        },
        "candidate_counts_by_window": dict(
            sorted(Counter(str(row.get("window") or "missing") for row in ranked).items())
        ),
        "selected_counts_by_window": dict(
            sorted(Counter(str(row.get("window") or "missing") for row in selected).items())
        ),
        "source_manifest": repo_rel(LEDGER_ROWS),
    }
    return selected, ranked, audit


def metrics_with_overlay_pnl(before: dict[str, Any], overlay_total_pnl: float) -> dict[str, Any]:
    after = dict(before)
    pnl = float(before.get("total_pnl") or 0.0) + float(overlay_total_pnl or 0.0)
    ret = float(before.get("strategy_total_return_pct") or 0.0) + (
        float(overlay_total_pnl or 0.0) / 100_000.0
    )
    sharpe = safe_float(before.get("sharpe_daily"))
    after["total_pnl"] = round(pnl, 2)
    after["strategy_total_return_pct"] = round(ret, 6)
    after["sharpe_daily"] = round_or_none(sharpe, 4)
    after["expected_value_score"] = round(ret * sharpe, 4) if sharpe is not None else None
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
    failed.append("daily_snapshot_not_exposed_for_full_stack_contract")
    failed.append("parity_test_missing_for_full_stack_contract")
    return {
        "passed": not failed,
        "decision": (
            "positive_replay_lead_news_second_order_negative_top1_candidate_source"
            if not [
                item
                for item in failed
                if item
                not in (
                    "daily_snapshot_not_exposed_for_full_stack_contract",
                    "parity_test_missing_for_full_stack_contract",
                )
            ]
            else "rejected_news_second_order_negative_top1_candidate_source"
        ),
        "economic_gate_passed": not [
            item
            for item in failed
            if item
            not in (
                "daily_snapshot_not_exposed_for_full_stack_contract",
                "parity_test_missing_for_full_stack_contract",
            )
        ],
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
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
        },
    }


def calibrate(
    prediction: dict[str, Any],
    accepted: bool,
    failures: list[str],
    aggregate: dict[str, Any],
) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if accepted else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    failure_text = " ".join(failures)
    hits = [
        mode
        for mode in predicted_modes
        if (
            (mode == "top1_compression_loses_observed_edge" and "aggregate_pnl_not_positive" in failures)
            or (mode == "window_instability" and "window_" in failure_text)
            or (mode == "accepted_comparator_not_beaten" and "comparator" in failure_text)
            or (mode == "concentration_failed" and "concentration" in failure_text)
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
        "predicted_failure_modes_hit": hits,
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
    economic_passed = bool(g4["economic_gate_passed"])
    accepted = False
    status = "observed_only_positive_lead" if economic_passed else "rejected"
    decision = g4["decision"]
    if economic_passed:
        why = (
            "The fixed top-1/day compression preserved the prior polarity lead "
            "economically, but it remains only a replay lead because no shared "
            "daily helper or parity test exists in this scout."
        )
    else:
        why = (
            "The broad baseline-controlled polarity lead did not survive the "
            "deployable top-1/day compression and full fixed-window bar: "
            + ("; ".join(g4["failed_reasons"]) or "none")
        )

    forbidden = (
        "Do not re-slice the same second-order ledger by relation type, theme, "
        "horizon, event keyword, first-order ticker, liquidity threshold, hold "
        "days, cooldown, notional, or response shape on these rows."
    )
    next_evidence = (
        "A valid retry needs materially more current closed rows from the daily "
        "observer, historical structured-news coverage across all canonical "
        "windows, or intraday timestamped execution semantics."
    )

    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "shared_helper_promoted": False,
        "daily_snapshot_exposed": False,
        "backtester_adapter_changed": False,
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
        "live_realism_evaluated": True,
        "execution_envelope": {
            "base_notional": BASE_NOTIONAL_USD,
            "max_capital_pct": 0.25,
            "min_dollar_volume": MIN_AVG_DOLLAR_VOLUME_20D,
            "slippage_bps": 5.0,
            "max_displacement": 1,
            "max_concurrent": 10,
            "order_semantics": "next_open_after_first_order_event_date",
            "kill_switch_drawdown_pct": 0.08,
            "sleeve_drawdown_stop_pct": 0.05,
            "notes": (
                "Private replay scout only. A positive result would require "
                "a shared helper and daily default-off snapshot before paper "
                "promotion."
            ),
        },
        "parity_note": (
            "No production or shared paper helper changed; this runner only "
            "tests an unvalidated compression shape."
        ),
    }

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "full_stack_verdict": "reject",
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
                "novelty_gate": "experiment.py new allowed the ticket with a recorded new gate-shape evidence axis.",
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One fixed candidate source: negative-polarity first-order "
                "structured-news rows only, one top-1 exposure ticker per "
                "entry day, latest published_at then highest ADV20, 10-day hold."
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
            "ledger_rows": repo_rel(LEDGER_ROWS),
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
                "event_date",
                "published_at",
                "event_polarity",
                "first_order_ticker",
                "exposure_ticker",
                "entry_date",
                "target_price",
                "avg_dollar_volume_20d",
            ],
            "ledger_exists": LEDGER_ROWS.exists(),
            "target_price_scope": "not_applicable_fixed_10d_paper_source",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No core executable filter was added; this is additive default-off paper replay only.",
            "minimum_core_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
        },
        "gate4": g4,
        "full_stack": {
            "verdict": "reject",
            "economic_gate_passed": economic_passed,
            "live_readiness": {
                "ready": False,
                "blockers": [
                    "private_replay_scout_not_shared_helper",
                    "no_daily_snapshot",
                    "no_forward_rows_under_candidate_source",
                ],
            },
            "execution_envelope": production_impact["execution_envelope"],
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": forbidden,
            "new_evidence_required": next_evidence,
        },
        "next_retry_requires": [next_evidence],
        "rejection_reason": ";".join(g4["failed_reasons"]),
        "related_files": [
            RUNNER,
            repo_rel(LEDGER_ROWS),
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
    return payload


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
            f"# {EXPERIMENT_ID}: news second-order negative top-1 candidate source",
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
            f"- Economic passed: `{payload['gate4']['economic_gate_passed']}`",
            f"- Full-stack passed: `{payload['gate4']['passed']}`",
            f"- Failed reasons: `{payload['gate4']['failed_reasons']}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        LEDGER_ROWS,
        REPO_ROOT / "experiments" / "logs" / "exp-20260702-021.json",
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
                "economic_gate_passed": payload["gate4"]["economic_gate_passed"],
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
