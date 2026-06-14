"""exp-20260614-027: TTM cash-conversion acceleration candidate pool.

Replay-only alpha search. The single decision hypothesis is a new PIT
Companyfacts quality discriminator for the rejected cash-conversion family:
current TTM operating-cash-flow / net-income quality should improve versus the
prior comparable TTM, not merely be statically high. This is not a deployment,
stop, threshold, hold, cooldown, or notional retry of exp-20260614-020/021/023,
nor the static TTM quality field from exp-20260614-025.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fundamental_growth_rs_paper_sleeve import load_companyfacts_rows  # noqa: E402
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH  # noqa: E402


EXPERIMENT_ID = "exp-20260614-027"
STEM = "ttm_cash_conversion_acceleration"
TRIAL_FAMILY = "ttm_cash_conversion_acceleration_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_ttm_cash_conversion_acceleration_top1_next_open_10d_v1"
CHANGED_VARIABLE = "ttm_cash_conversion_acceleration_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

WAREHOUSE = DEFAULT_WAREHOUSE_PATH
SECTOR_MAP = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_027_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

FY_DURATION_MIN = 340
FY_DURATION_MAX = 380
YTD_DURATION_MIN = 120
YTD_DURATION_MAX = 320
MAX_CURRENT_TTM_FACT_AGE_DAYS = 260
MIN_CURRENT_TTM_CASH_CONVERSION = 1.00
MAX_CURRENT_TTM_ACCRUALS_TO_ASSETS = 0.00
MIN_CASH_CONVERSION_ACCELERATION = 0.10
MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT = 0.005

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = -0.05
MIN_SIGNAL_RETURN = -0.03
MAX_SIGNAL_RETURN = 0.06
MIN_CLOSE_LOCATION = 0.40
MAX_REALIZED_VOL_20D = 0.10

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

WINDOWS: "OrderedDict[str, dict[str, str]]" = framework.WINDOWS
COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "aggregate_expected_value_delta": 0.1608,
    "aggregate_pnl_delta": 2248.98,
}
DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "aggregate_expected_value_delta": 0.5286,
    "aggregate_pnl_delta": 10432.91,
}

PREDICTION = {
    "success_probability": 0.21,
    "expected_ev_delta": 0.35,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "drawdown_drift_too_high",
        "window_regression",
        "static_cash_conversion_overlap",
        "thin_acceleration_sample",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The annual and TTM cash-conversion quality scouts were directionally "
        "strong but rejected on drawdown; requiring cash conversion to "
        "accelerate versus the prior comparable TTM is a distinct PIT "
        "Companyfacts field, not a deployment, stop, threshold, hold, cooldown, "
        "or notional retry."
    ),
    "recorded_at": "2026-06-14T21:04:24+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_companyfacts": True,
    "uses_free_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing annual/YTD/prior comparable net_income or operating_cash_flow, "
            "missing assets, missing OHLCV, missing next open, or missing 10d "
            "exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "TTM cash-conversion acceleration gate, liquid SPY-relative "
        "confirmation, cooldown, next-open paper entry, 10-day exit, costs, and "
        "concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: production-universe names whose current PIT TTM "
        "operating-cash-flow coverage of net income improves versus prior "
        "comparable TTM should represent accelerating earnings quality and "
        "reduce the tail problem from static cash-conversion quality."
    ),
    "2_history_check": {
        "exp-20260614-020": (
            "Annual accruals/cash-conversion was all-window positive but "
            "rejected because drawdown drift was +5.22pp."
        ),
        "exp-20260614-021": (
            "Low deployment on the annual field still regressed old_thin and "
            "failed drawdown, so this run does not retune deployment."
        ),
        "exp-20260614-023": (
            "A 7% daily-close protective stop failed Gate 4, so this run does "
            "not retune exits or stop levels."
        ),
        "exp-20260614-024": (
            "Quarterly cash-conversion improvement was too thin and "
            "concentrated."
        ),
        "exp-20260614-025": (
            "Static TTM same-period accruals quality improved all windows but "
            "was rejected on +3.29pp drawdown drift. This run changes the "
            "information field to acceleration versus prior comparable TTM."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression "
        "and distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_027_ttm_cash_conversion_acceleration.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _configure_sleeve_globals() -> None:
    sleeve.EXPERIMENT_ID = EXPERIMENT_ID
    sleeve.STEM = STEM
    sleeve.TRIAL_FAMILY = TRIAL_FAMILY
    sleeve.CHANGED_VARIABLE = CHANGED_VARIABLE
    sleeve.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    sleeve.HOLD_DAYS = HOLD_DAYS
    sleeve.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    sleeve.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    sleeve.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    sleeve.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    sleeve.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    sleeve.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    sleeve.OUT_DIR = OUT_DIR
    sleeve.OUT_JSON = OUT_JSON
    sleeve.LOG_JSON = LOG_JSON
    sleeve.TICKET_JSON = TICKET_JSON
    sleeve.CARD_MD = CARD_MD
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _days_between(later: str, earlier: str) -> int:
    return (framework._parse_date(later) - framework._parse_date(earlier)).days


def _load_sector_entries() -> dict[str, dict[str, Any]]:
    if not SECTOR_MAP.exists():
        return {}
    payload = json.loads(SECTOR_MAP.read_text(encoding="utf-8"))
    entries = payload.get("entries", payload)
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in entries.items():
        if isinstance(meta, dict):
            out[str(ticker).upper()] = {
                "sector": meta.get("sector"),
                "industry": meta.get("industry"),
                "sector_coverage_status": meta.get("status"),
            }
    return out


def _annual_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        try:
            duration = int(raw.get("duration_days"))
        except (TypeError, ValueError):
            continue
        if not (FY_DURATION_MIN <= duration <= FY_DURATION_MAX):
            continue
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        value = _float_or_none(raw.get("value"))
        if filed and end and value is not None:
            facts.append({"filed": filed, "end": end, "value": value, "duration_days": duration})
    facts.sort(key=lambda row: (row["filed"], row["end"]))
    return facts


def _ytd_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        try:
            duration = int(raw.get("duration_days"))
        except (TypeError, ValueError):
            continue
        if not (YTD_DURATION_MIN <= duration <= YTD_DURATION_MAX):
            continue
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        value = _float_or_none(raw.get("value"))
        if filed and end and value is not None:
            facts.append({"filed": filed, "end": end, "value": value, "duration_days": duration})
    facts.sort(key=lambda row: (row["filed"], row["end"], row["duration_days"]))
    return facts


def _instant_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        filed = str(raw.get("filed") or "")[:10]
        value = _float_or_none(raw.get("value"))
        if filed and value is not None:
            facts.append({"filed": filed, "value": value})
    facts.sort(key=lambda row: row["filed"])
    return facts


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in companyfacts_rows:
        ticker = str(raw.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker].append(raw)

    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    stats: Counter[str] = Counter()
    for ticker, rows in by_ticker.items():
        annual_ni = _annual_facts(rows, "net_income")
        annual_ocf = _annual_facts(rows, "operating_cash_flow")
        ytd_ni = _ytd_facts(rows, "net_income")
        ytd_ocf = _ytd_facts(rows, "operating_cash_flow")
        assets = _instant_facts(rows, "assets")
        if not annual_ni or not annual_ocf or not ytd_ni or not ytd_ocf or not assets:
            stats["tickers_missing_required_facts"] += 1
            continue
        index[ticker] = {
            "annual_net_income": annual_ni,
            "annual_operating_cash_flow": annual_ocf,
            "ytd_net_income": ytd_ni,
            "ytd_operating_cash_flow": ytd_ocf,
            "assets": assets,
        }
        stats["tickers_with_ttm_acceleration_facts"] += 1
    return index, {
        "companyfacts_rows_loaded": len(companyfacts_rows),
        "tickers_seen": len(by_ticker),
        **dict(stats),
    }


def _latest_on_or_before(facts: list[dict[str, Any]], asof: str) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof:
            chosen = fact
        else:
            break
    return chosen


def _matched_on_or_before(
    facts: list[dict[str, Any]], asof: str, end: str
) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof and fact["end"] == end:
            chosen = fact
    return chosen


def _latest_annual_before_ytd(
    facts: list[dict[str, Any]], asof: str, ytd_end: str
) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof and fact["end"] < ytd_end:
            chosen = fact
    return chosen


def _prior_comparable_ytd(
    facts: list[dict[str, Any]], asof: str, current: dict[str, Any]
) -> dict[str, Any] | None:
    current_end = framework._parse_date(current["end"])
    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current["end"]:
            continue
        gap = (current_end - framework._parse_date(fact["end"])).days
        duration_gap = abs(int(fact["duration_days"]) - int(current["duration_days"]))
        if 250 <= gap <= 450 and duration_gap <= 25:
            candidates.append((duration_gap, abs(gap - 365), fact["filed"], fact))
    candidates.sort(key=lambda row: (row[0], row[1], row[2]))
    return candidates[0][3] if candidates else None


def _ttm_bundle(
    *,
    asof: str,
    current_ytd_ni: dict[str, Any],
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_ytd_ocf = _matched_on_or_before(
        facts["ytd_operating_cash_flow"], asof, current_ytd_ni["end"]
    )
    if current_ytd_ocf is None:
        return None
    prior_ytd_ni = _prior_comparable_ytd(facts["ytd_net_income"], asof, current_ytd_ni)
    if prior_ytd_ni is None:
        return None
    prior_ytd_ocf = _matched_on_or_before(
        facts["ytd_operating_cash_flow"], asof, prior_ytd_ni["end"]
    )
    if prior_ytd_ocf is None:
        return None
    annual_ni = _latest_annual_before_ytd(
        facts["annual_net_income"], asof, current_ytd_ni["end"]
    )
    if annual_ni is None:
        return None
    annual_ocf = _matched_on_or_before(
        facts["annual_operating_cash_flow"], asof, annual_ni["end"]
    )
    if annual_ocf is None:
        return None
    ttm_ni = annual_ni["value"] + current_ytd_ni["value"] - prior_ytd_ni["value"]
    ttm_ocf = annual_ocf["value"] + current_ytd_ocf["value"] - prior_ytd_ocf["value"]
    if ttm_ni <= 0.0 or ttm_ocf <= 0.0:
        return None
    return {
        "ttm_net_income": ttm_ni,
        "ttm_operating_cash_flow": ttm_ocf,
        "annual_net_income": annual_ni,
        "annual_operating_cash_flow": annual_ocf,
        "current_ytd_net_income": current_ytd_ni,
        "current_ytd_operating_cash_flow": current_ytd_ocf,
        "prior_ytd_net_income": prior_ytd_ni,
        "prior_ytd_operating_cash_flow": prior_ytd_ocf,
        "cash_conversion_ratio": ttm_ocf / ttm_ni,
    }


def _quality_for_asof(
    *,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_ytd_ni = _latest_on_or_before(facts["ytd_net_income"], asof)
    if current_ytd_ni is None:
        return None
    if _days_between(asof, current_ytd_ni["filed"]) > MAX_CURRENT_TTM_FACT_AGE_DAYS:
        return None
    current = _ttm_bundle(asof=asof, current_ytd_ni=current_ytd_ni, facts=facts)
    if current is None:
        return None
    prior_ytd_ni = current["prior_ytd_net_income"]
    prior = _ttm_bundle(asof=asof, current_ytd_ni=prior_ytd_ni, facts=facts)
    if prior is None:
        return None
    assets = _latest_on_or_before(facts["assets"], asof)
    if assets is None or assets["value"] <= 0.0:
        return None

    current_accruals = (
        current["ttm_net_income"] - current["ttm_operating_cash_flow"]
    ) / assets["value"]
    prior_accruals = (
        prior["ttm_net_income"] - prior["ttm_operating_cash_flow"]
    ) / assets["value"]
    current_conversion = current["cash_conversion_ratio"]
    prior_conversion = prior["cash_conversion_ratio"]
    acceleration = current_conversion - prior_conversion
    accrual_improvement = prior_accruals - current_accruals

    if current_conversion < MIN_CURRENT_TTM_CASH_CONVERSION:
        return None
    if current_accruals > MAX_CURRENT_TTM_ACCRUALS_TO_ASSETS:
        return None
    if acceleration < MIN_CASH_CONVERSION_ACCELERATION:
        return None
    if accrual_improvement < MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT:
        return None

    annual_ni = current["annual_net_income"]
    annual_ocf = current["annual_operating_cash_flow"]
    current_ytd_ocf = current["current_ytd_operating_cash_flow"]
    current_ytd_ni = current["current_ytd_net_income"]
    prior_ytd_ocf = current["prior_ytd_operating_cash_flow"]
    prior_ytd_ni = current["prior_ytd_net_income"]
    return {
        "current_ttm_net_income": _round(current["ttm_net_income"], 2),
        "current_ttm_operating_cash_flow": _round(current["ttm_operating_cash_flow"], 2),
        "prior_ttm_net_income": _round(prior["ttm_net_income"], 2),
        "prior_ttm_operating_cash_flow": _round(prior["ttm_operating_cash_flow"], 2),
        "current_ttm_cash_conversion_ratio": _round(current_conversion, 6),
        "prior_ttm_cash_conversion_ratio": _round(prior_conversion, 6),
        "cash_conversion_acceleration": _round(acceleration, 6),
        "current_ttm_accruals_to_assets": _round(current_accruals, 6),
        "prior_ttm_accruals_to_assets": _round(prior_accruals, 6),
        "accruals_to_assets_improvement": _round(accrual_improvement, 6),
        "assets_filed": assets["filed"],
        "total_assets": _round(assets["value"], 2),
        "current_ytd_end": current_ytd_ni["end"],
        "prior_ytd_end": prior_ytd_ni["end"],
        "annual_period_end": annual_ni["end"],
        "current_ytd_net_income_filed": current_ytd_ni["filed"],
        "current_ytd_operating_cash_flow_filed": current_ytd_ocf["filed"],
        "prior_ytd_net_income_filed": prior_ytd_ni["filed"],
        "prior_ytd_operating_cash_flow_filed": prior_ytd_ocf["filed"],
        "annual_net_income_filed": annual_ni["filed"],
        "annual_operating_cash_flow_filed": annual_ocf["filed"],
        "current_fact_age_days": _days_between(asof, current_ytd_ni["filed"]),
    }


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=120)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = shadow._value(rows[idx - lookback], "Close")
    close = shadow._value(rows[idx], "Close")
    if prior is None or prior <= 0.0 or close is None:
        return None
    return (close / prior) - 1.0


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    return framework._daily_return(rows, idx)


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    return framework._avg_dollar_volume(rows, idx, lookback=lookback)


def _volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    current = shadow._value(rows[idx], "Volume")
    if current is None:
        return None
    prior = [shadow._value(row, "Volume") for row in rows[idx - lookback : idx]]
    if any(value is None for value in prior):
        return None
    avg = sum(float(value) for value in prior if value is not None) / len(prior)
    return current / avg if avg > 0.0 else None


def _close_location(row: dict[str, Any]) -> float | None:
    high = shadow._value(row, "High")
    low = shadow._value(row, "Low")
    close = shadow._value(row, "Close")
    if high is None or low is None or close is None:
        return None
    spread = high - low
    if spread <= 0.0:
        return 0.5
    return (close - low) / spread


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    returns = [_daily_return(rows, day_idx) for day_idx in range(idx - lookback + 1, idx + 1)]
    if any(value is None for value in returns):
        return None
    values = [float(value) for value in returns if value is not None]
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _price_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = shadow._series(snapshot, ticker)
    spy_rows = shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = shadow._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = _daily_return(rows, idx)
    if signal_return is None or signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    ret20 = _ret(rows, idx, 20)
    ret60 = _ret(rows, idx, 60)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    spy_ret60 = _ret(spy_rows, spy_idx, 60)
    if ret20 is None or ret60 is None or spy_ret20 is None or spy_ret60 is None:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    close_location = _close_location(rows[idx])
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    realized_vol = _realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None
    return {
        "candidate_close": _round(close, 4),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret60": _round(ret60, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": _round(ret60_excess_spy, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(_volume_ratio(rows, idx), 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = shadow._baseline_entries(before_result)
    indices = {ticker: shadow._row_index(shadow._series(snapshot, ticker)) for ticker in snapshot}
    dates = [
        date_value
        for date_value in shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    scan: Counter[str] = Counter()
    tickers_with_quality: set[str] = set()
    for signal_date in dates:
        for ticker, facts in quality_index.items():
            if ticker not in snapshot:
                continue
            quality = _quality_for_asof(asof=signal_date, facts=facts)
            if quality is None:
                scan["failed_quality_gate"] += 1
                continue
            tickers_with_quality.add(ticker)
            price = _price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if price is None:
                scan["failed_price_confirmation"] += 1
                continue
            sector_meta = sector_entries.get(ticker, {})
            score = (
                1.40 * float(quality["cash_conversion_acceleration"] or 0.0)
                + 0.35 * float(quality["current_ttm_cash_conversion_ratio"] or 0.0)
                + 0.75 * float(quality["accruals_to_assets_improvement"] or 0.0)
                + 1.60 * float(price["candidate_ret20_excess_spy"] or 0.0)
                + 0.80 * float(price["candidate_ret60_excess_spy"] or 0.0)
                + 0.20 * float(price["candidate_close_location"] or 0.0)
                - 0.50 * float(price["candidate_realized_vol_20d"] or 0.0)
            )
            ab_entries = entries_by_date.get(signal_date, [])
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "TTM_CASH_CONVERSION_ACCELERATION_PAPER",
                    "source_rule_version": RULE_VERSION,
                    "rule_version": RULE_VERSION,
                    "selection_rule_version": RULE_VERSION,
                    "candidate_score": _round(score, 6),
                    "known_at": "annual_plus_ytd_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "trade_enabled": False,
                    "uses_free_ohlcv": True,
                    "uses_free_sec_companyfacts": True,
                    "uses_llm": False,
                    "sector": sector_meta.get("sector"),
                    "industry": sector_meta.get("industry"),
                    "sector_coverage_status": sector_meta.get("sector_coverage_status"),
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        trade.get("ticker") == ticker for trade in ab_entries
                    ),
                    **quality,
                    **price,
                }
            )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("cash_conversion_acceleration") or 0.0),
            -float(row.get("candidate_ret20_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    return candidates, {
        "scanned_trading_days": len(dates),
        "eligible_quality_tickers": len(tickers_with_quality),
        "candidate_signal_days": len({row["date"] for row in candidates}),
        "candidate_tickers": len({row["ticker"] for row in candidates}),
        "qualified_candidate_rows": len(candidates),
        "rule_version": RULE_VERSION,
        "min_current_ttm_cash_conversion": MIN_CURRENT_TTM_CASH_CONVERSION,
        "max_current_ttm_accruals_to_assets": MAX_CURRENT_TTM_ACCRUALS_TO_ASSETS,
        "min_cash_conversion_acceleration": MIN_CASH_CONVERSION_ACCELERATION,
        "min_accruals_to_assets_improvement": MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT,
        **dict(scan),
    }


def _select_paper_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    dates = shadow._trading_dates(snapshot)
    date_pos = {date_value: idx for idx, date_value in enumerate(dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    for row in candidates:
        signal_date = str(row.get("date") or "")
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = sleeve._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    return selected, filtered


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    target_windows = target_summary["windows_with_target_trades"]
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
    if aggregate["expected_value_score_delta_sum"] <= COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if aggregate["expected_value_score_delta_sum"] <= DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_ttm_cash_conversion_acceleration"
        if passed
        else "rejected_ttm_cash_conversion_acceleration_candidate_pool"
    )
    return {
        "passed": passed,
        "decision": decision,
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
        "minimum_core_survival_rate": _round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    _configure_sleeve_globals()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    companyfacts_rows = load_companyfacts_rows(
        max_filed=max(cfg["end"] for cfg in WINDOWS.values()),
        tickers=universe,
    )
    quality_index, quality_summary = _build_quality_index(companyfacts_rows)
    sector_entries = _load_sector_entries()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] baseline core replay and TTM cash-conversion acceleration")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = _load_window_snapshot(cfg=cfg, eligible_tickers=set(quality_index))
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "quality_index_ticker_count": len(quality_index),
            "source": _repo_rel(WAREHOUSE),
        }
        candidates, scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            before_result=before_result,
            quality_index=quality_index,
            sector_entries=sector_entries,
        )
        selected_trades, filtered_candidates = _select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        context_scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = sleeve._aggregate(window_rows)
    target_summary = sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    status = "observed_only_positive_replay_lead" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": _round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    failed_reasons = gate4["failed_reasons"]
    if gate4["passed"]:
        interpretation = (
            "The acceleration field passed the numeric replay gate, but remains "
            "only a replay lead because no shared daily/backtest helper was "
            "promoted."
        )
    else:
        interpretation = (
            "The TTM cash-conversion acceleration field did not clear Gate 4 "
            f"(failed: {', '.join(failed_reasons) or 'none'}). It is not "
            "retained or promoted."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": gate4["passed"],
        "hypothesis": (
            "PIT TTM cash-flow acceleration may sharpen the rejected "
            "cash-conversion quality lead by requiring current same-period TTM "
            "cash conversion to improve versus prior TTM, isolating earnings "
            "quality acceleration rather than static quality."
        ),
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_companyfacts_quality_candidate_pool",
        "new_evidence_type": "free_sec_companyfacts_ttm_cash_conversion_acceleration_plus_ohlcv",
        "nearby_prior_experiments": [
            "exp-20260614-020",
            "exp-20260614-021",
            "exp-20260614-023",
            "exp-20260614-024",
            "exp-20260614-025",
        ],
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "low",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": WINDOWS,
            "candidate_ohlcv_source": _repo_rel(WAREHOUSE),
            "companyfacts_source": "data/non_ohlcv/sec_companyfacts_selected_*.jsonl",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Current and prior comparable TTM net_income and "
                "operating_cash_flow are constructed point-in-time from "
                "SEC-filed annual and YTD Companyfacts. Price confirmation uses "
                "only signal-date OHLCV. Paper entry is the next available open "
                "with existing entry slippage; exit is the close 10 trading "
                "days after the signal with target-side sell slippage and "
                "ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "fy_duration_min": FY_DURATION_MIN,
            "fy_duration_max": FY_DURATION_MAX,
            "ytd_duration_min": YTD_DURATION_MIN,
            "ytd_duration_max": YTD_DURATION_MAX,
            "max_current_ttm_fact_age_days": MAX_CURRENT_TTM_FACT_AGE_DAYS,
            "min_current_ttm_cash_conversion": MIN_CURRENT_TTM_CASH_CONVERSION,
            "max_current_ttm_accruals_to_assets": MAX_CURRENT_TTM_ACCRUALS_TO_ASSETS,
            "min_cash_conversion_acceleration": MIN_CASH_CONVERSION_ACCELERATION,
            "min_accruals_to_assets_improvement": MIN_ACCRUALS_TO_ASSETS_IMPROVEMENT,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "SEC companyfacts canonical net_income (annual and YTD)",
                "SEC companyfacts canonical operating_cash_flow (annual and YTD)",
                "SEC companyfacts canonical assets",
                "SEC companyfacts filed date, period end, and duration_days",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV for relative strength",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": True,
            "note": (
                "No new core filter or entry rule was added. The candidate "
                "source is additive default-off paper, so core survival is "
                "unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "quality_index_summary": quality_summary,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(failed_reasons),
        "next_evidence_needed": (
            "A retry needs closed forward replacement-value rows or a materially "
            "different free data context such as borrow availability, options "
            "outcome, or ownership crowding/underownership. Do not sweep TTM "
            "duration ranges, acceleration thresholds, accrual thresholds, "
            "fact freshness, RS/close/volume guards, top-N, hold, cooldown, or "
            "notional on the same frozen windows."
        ),
        "post_run_reflection": {
            "why_result_happened": interpretation,
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
                "max drawdown drift {:+.4f}; {} paper trades.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                    target_summary["total_trade_count"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping TTM duration ranges, acceleration "
                "threshold, accruals/assets threshold, fact freshness, "
                "RS/close/volume/vol guards, top-N, hold days, cooldown, or "
                "notional on these frozen windows."
            ),
            "new_evidence_required": (
                "Closed forward replacement-value rows or a materially "
                "different PIT data edge, not another cash-conversion threshold "
                "or risk-envelope sweep."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} TTM Cash-Conversion Acceleration",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get("eligible_quality_tickers"),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "anti_js": "No JavaScript was used.",
    }


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
