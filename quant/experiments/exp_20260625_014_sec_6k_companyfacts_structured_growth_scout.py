"""exp-20260625-014: SEC 6-K Companyfacts structured growth scout.

Private replay scout for a blocked 6-K text alpha. Historical 6-K filing text is
not locally replayable, but the SEC Companyfacts cache contains form-scoped 6-K
XBRL fact rows. This runner tests one fixed candidate-pool hypothesis:
same-accession 6-K/6-KA revenue plus profitability growth, confirmed by liquid
price action, can add next-open 10-trading-day paper alpha.

No production code, shared policy, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. Positive replay would only be
a lead requiring a shared default-off helper and daily snapshot.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for import_path in (SCRIPTS_DIR, QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402
import exp_20260426_041_opening_range_continuation_shadow as shadow  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as sleeve  # noqa: E402
from data_layer import get_universe  # noqa: E402
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH  # noqa: E402
from sec_ticker_map import load_company_ticker_map, normalize_cik  # noqa: E402


EXPERIMENT_ID = "exp-20260625-014"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "sec_6k_companyfacts_structured_growth_scout"
RUNNER = f"quant/experiments/exp_20260625_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

STEM = "sec_6k_companyfacts_structured_growth_scout"
TRIAL_FAMILY = "sec_6k_companyfacts_structured_financial_growth_candidate_pool"
TRIAL_VARIANT_ID = "form_scoped_6k_xbrl_growth_top1_10d_v1"
CHANGED_VARIABLE = "sec_6k_companyfacts_structured_financial_growth_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
MECHANISM_FAMILY = "candidate_pool_private_replay_scout"

WAREHOUSE = DEFAULT_WAREHOUSE_PATH
COMPANYFACTS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260625_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = -0.005
MAX_SIGNAL_RETURN = 0.12
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = -0.03
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.50
MAX_VOLUME_RATIO_20D = 5.0
MAX_REALIZED_VOL_20D = 0.09

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

SIX_K_FORMS = {"6-K", "6-K/A", "6-KA"}
TOPLINE_COMPONENTS = {"revenue", "gross_profit"}
CORE_PROFIT_COMPONENTS = {"operating_profit", "net_income", "operating_cash_flow"}
COMPONENT_GROWTH_THRESHOLDS = {
    "revenue": 0.08,
    "gross_profit": 0.10,
    "operating_profit": 0.12,
    "net_income": 0.12,
    "operating_cash_flow": 0.10,
}
TAG_TO_COMPONENT = {
    ("ifrs-full", "Revenue"): "revenue",
    ("ifrs-full", "RevenueFromInterest"): "revenue",
    ("ifrs-full", "RevenueFromContractsWithCustomers"): "revenue",
    ("ifrs-full", "RevenueFromContractsWithCustomersExcludingAssessedTax"): "revenue",
    ("us-gaap", "Revenues"): "revenue",
    ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"): "revenue",
    ("us-gaap", "SalesRevenueNet"): "revenue",
    ("us-gaap", "SalesRevenueGoodsNet"): "revenue",
    ("us-gaap", "SalesRevenueServicesNet"): "revenue",
    ("ifrs-full", "GrossProfit"): "gross_profit",
    ("us-gaap", "GrossProfit"): "gross_profit",
    ("ifrs-full", "ProfitLossFromOperatingActivities"): "operating_profit",
    ("ifrs-full", "OperatingProfitLoss"): "operating_profit",
    ("us-gaap", "OperatingIncomeLoss"): "operating_profit",
    ("ifrs-full", "ProfitLoss"): "net_income",
    ("ifrs-full", "ProfitLossAttributableToOwnersOfParent"): "net_income",
    (
        "ifrs-full",
        "ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity",
    ): "net_income",
    ("us-gaap", "NetIncomeLoss"): "net_income",
    ("us-gaap", "ProfitLoss"): "net_income",
    ("ifrs-full", "CashFlowsFromUsedInOperatingActivities"): "operating_cash_flow",
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"): "operating_cash_flow",
}

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
EVENT_SCAN_START = min(date.fromisoformat(row["start"]) for row in WINDOWS.values())
EVENT_SCAN_END = max(date.fromisoformat(row["end"]) for row in WINDOWS.values())

HYPOTHESIS = (
    "SEC 6-K form-scoped structured Companyfacts XBRL growth facts may identify "
    "ADR interim financial-result drift when historical filing text is "
    "unavailable, but must first pass a private canonical replay scout."
)
ALPHA_HYPOTHESIS = (
    "candidate-pool alpha: same-accession 6-K/6-KA XBRL facts showing revenue "
    "plus profitability growth, delayed one trading day from filed date and "
    "confirmed by liquid relative price action, may produce next-open 10-day "
    "paper alpha in foreign issuers."
)
NEW_EVIDENCE_AXIS = (
    "Machine-checkable new evidence axis: form-scoped SEC Companyfacts XBRL facts "
    "where fact.form is 6-K/6-KA, tied to filed-date/accession metadata, replacing "
    "the missing historical 6-K text surface; not another generic Companyfacts "
    "ratio field or threshold sweep."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-016",
    "exp-20260624-024",
    "exp-20260625-011",
    "exp-20260625-006",
]

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "companyfacts_source_saturation",
        "thin_6k_fact_coverage",
        "window_regression",
        "accepted_comparator_not_beaten",
        "foreign_issuer_liquidity_gap",
    ],
    "confidence_reason": (
        "The 6-K text alpha is blocked by zero historical text rows, but local "
        "SEC Companyfacts cache contains form=6-K XBRL facts with filed-date and "
        "accession metadata. This fixed scout uses same-accession XBRL revenue "
        "plus profitability growth and conservative next-day price confirmation."
    ),
    "recorded_at": "2026-06-25T13:06:00+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "daily_snapshot_exposed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "production_watchlist_changed": False,
    "uses_free_sec_companyfacts": True,
    "uses_form_scoped_6k_facts": True,
    "uses_llm": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "replay_only": True,
    "adapter_status": "private_replay_only_no_live_adapter",
    "parity_note": (
        "This is an experiment-owned private replay scout. A positive result "
        "would require a shared default-off helper that computes the same "
        "form-scoped Companyfacts event surface, one-trading-day filing delay, "
        "price/liquidity gates, next-open paper entry, 10-trading-day exit, "
        "cost model, cooldown, and concentration checks before any daily report, "
        "candidate priority, sizing, watchlist, paper ledger, or order surface "
        "could change."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe(payload: Any) -> Any:
    if isinstance(payload, OrderedDict):
        return {str(key): safe(value) for key, value in payload.items()}
    if isinstance(payload, Counter):
        return {str(key): safe(value) for key, value in payload.items()}
    if isinstance(payload, defaultdict):
        return {str(key): safe(value) for key, value in payload.items()}
    if isinstance(payload, dict):
        return {str(key): safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(safe(value) for value in payload)
    if isinstance(payload, Path):
        return repo_rel(payload)
    if isinstance(payload, date):
        return payload.isoformat()
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return default


def upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configure_sleeve_globals() -> None:
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
    sleeve.EXPERIMENT_LOG = EXPERIMENT_LOG_JSONL


def load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = date.fromisoformat(cfg["start"]) - timedelta(days=100)
    end = date.fromisoformat(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    with sqlite3.connect(WAREHOUSE) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, start.isoformat(), end.isoformat()]
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


def value(row: dict[str, Any], key: str) -> float | None:
    return shadow._value(row, key)


def daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = value(rows[idx - 1], "Close")
    close = value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = value(rows[idx - lookback], "Close")
    close = value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = value(row, "Close")
        volume = value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    current = value(rows[idx], "Volume")
    if current is None:
        return None
    prior = [value(row, "Volume") for row in rows[idx - lookback : idx]]
    if any(item is None for item in prior):
        return None
    average = sum(float(item) for item in prior if item is not None) / len(prior)
    if average <= 0:
        return None
    return current / average


def close_location(row: dict[str, Any]) -> float | None:
    high = value(row, "High")
    low = value(row, "Low")
    close = value(row, "Close")
    if high is None or low is None or close is None:
        return None
    span = high - low
    if span <= 0:
        return 0.5
    return (close - low) / span


def realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    values = [daily_return(rows, pos) for pos in range(idx - lookback + 1, idx + 1)]
    if any(item is None for item in values):
        return None
    valid = [float(item) for item in values if item is not None]
    mean_value = sum(valid) / len(valid)
    variance = sum((item - mean_value) ** 2 for item in valid) / len(valid)
    return math.sqrt(variance)


def fact_value(raw: Any) -> float | None:
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def component_compare(
    *,
    component: str,
    taxonomy: str,
    tag: str,
    unit: str,
    current: dict[str, Any],
    prior: dict[str, Any],
) -> dict[str, Any] | None:
    current_value = fact_value(current.get("val"))
    prior_value = fact_value(prior.get("val"))
    if current_value is None or prior_value is None:
        return None
    threshold = COMPONENT_GROWTH_THRESHOLDS[component]
    growth = None
    turnaround = False
    passed = False
    if prior_value > 0 and current_value > 0:
        growth = (current_value / prior_value) - 1.0
        passed = growth >= threshold
    elif component in CORE_PROFIT_COMPONENTS and prior_value <= 0 < current_value:
        turnaround = True
        passed = True

    if not passed and growth is None:
        component_score = 0.0
    elif turnaround:
        component_score = 0.25
    else:
        component_score = min(max(float(growth or 0.0), 0.0), 0.75)
    if passed and component in CORE_PROFIT_COMPONENTS:
        component_score += 0.10

    return {
        "component": component,
        "taxonomy": taxonomy,
        "tag": tag,
        "unit": unit,
        "current_end": current["end"].isoformat(),
        "prior_end": prior["end"].isoformat(),
        "current_value": round_float(current_value, 2),
        "prior_value": round_float(prior_value, 2),
        "growth": round_float(growth, 6),
        "turnaround": turnaround,
        "threshold": threshold,
        "passed": passed,
        "component_score": round_float(component_score, 6),
    }


def build_event_surface() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ticker_map = load_company_ticker_map()
    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    stats: dict[str, Any] = {
        "source": repo_rel(COMPANYFACTS_DIR),
        "scan_start": EVENT_SCAN_START.isoformat(),
        "scan_end": EVENT_SCAN_END.isoformat(),
        "companyfact_files_scanned": 0,
        "files_with_6k_financial_facts": 0,
        "mapped_tickers_with_6k_financial_facts": 0,
        "raw_6k_financial_fact_rows": 0,
        "same_accession_comparisons": 0,
        "growth_gate_event_rows": 0,
        "forms": sorted(SIX_K_FORMS),
        "component_thresholds": COMPONENT_GROWTH_THRESHOLDS,
        "tag_component_map": {
            f"{taxonomy}:{tag}": component
            for (taxonomy, tag), component in sorted(TAG_TO_COMPONENT.items())
        },
        "component_fact_rows": Counter(),
        "form_rows": Counter(),
        "file_skip_reasons": Counter(),
        "comparison_skip_reasons": Counter(),
    }
    tickers_with_rows: set[str] = set()

    for path in sorted(COMPANYFACTS_DIR.glob("CIK*.json")):
        stats["companyfact_files_scanned"] += 1
        payload = read_json(path, default=None)
        if not isinstance(payload, dict):
            stats["file_skip_reasons"]["invalid_json"] += 1
            continue
        cik = normalize_cik(payload.get("cik") or path.stem.replace("CIK", ""))
        mapping = ticker_map.get(cik or "")
        ticker = str((mapping or {}).get("ticker") or "").upper()
        if not ticker:
            stats["file_skip_reasons"]["missing_ticker_mapping"] += 1
            continue
        if "." in ticker or "-" in ticker:
            stats["file_skip_reasons"]["non_common_ticker_symbol"] += 1
            continue

        groups: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        facts = payload.get("facts") or {}
        if not isinstance(facts, dict):
            stats["file_skip_reasons"]["missing_facts"] += 1
            continue
        for taxonomy, tags in facts.items():
            if not isinstance(tags, dict):
                continue
            taxonomy_text = str(taxonomy)
            for tag, meta in tags.items():
                component = TAG_TO_COMPONENT.get((taxonomy_text, str(tag)))
                if component is None or not isinstance(meta, dict):
                    continue
                units = meta.get("units")
                if not isinstance(units, dict):
                    continue
                for unit, rows in units.items():
                    if not isinstance(rows, list):
                        continue
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        form = str(row.get("form") or "").upper()
                        if form not in SIX_K_FORMS:
                            continue
                        filed = parse_date(row.get("filed"))
                        if filed is None or filed < EVENT_SCAN_START or filed > EVENT_SCAN_END:
                            continue
                        end = parse_date(row.get("end"))
                        accession = str(row.get("accn") or "").strip()
                        value_raw = fact_value(row.get("val"))
                        if end is None or not accession or value_raw is None:
                            stats["comparison_skip_reasons"]["missing_fact_fields"] += 1
                            continue
                        fp = str(row.get("fp") or "").upper()
                        groups[(accession, component, taxonomy_text, str(tag), str(unit), fp)].append(
                            {
                                "ticker": ticker,
                                "cik": cik,
                                "entity_name": payload.get("entityName")
                                or (mapping or {}).get("company_title"),
                                "accession": accession,
                                "form": form,
                                "filed": filed,
                                "end": end,
                                "fy": row.get("fy"),
                                "fp": fp,
                                "val": value_raw,
                            }
                        )
                        stats["raw_6k_financial_fact_rows"] += 1
                        stats["component_fact_rows"][component] += 1
                        stats["form_rows"][form] += 1

        if not groups:
            continue
        stats["files_with_6k_financial_facts"] += 1
        tickers_with_rows.add(ticker)
        for (accession, component, taxonomy, tag, unit, fp), rows in groups.items():
            rows_sorted = sorted(rows, key=lambda item: item["end"])
            current = rows_sorted[-1]
            prior_candidates = [
                item
                for item in rows_sorted[:-1]
                if 250 <= (current["end"] - item["end"]).days <= 470
            ]
            if not prior_candidates:
                stats["comparison_skip_reasons"]["missing_same_accession_yoy_prior"] += 1
                continue
            prior = prior_candidates[-1]
            comparison = component_compare(
                component=component,
                taxonomy=taxonomy,
                tag=tag,
                unit=unit,
                current=current,
                prior=prior,
            )
            if comparison is None:
                stats["comparison_skip_reasons"]["invalid_comparison"] += 1
                continue
            stats["same_accession_comparisons"] += 1
            key = (ticker, current["filed"].isoformat(), accession)
            event = events.setdefault(
                key,
                {
                    "ticker": ticker,
                    "cik": current["cik"],
                    "company_name": current["entity_name"],
                    "filed_date": current["filed"].isoformat(),
                    "accession": accession,
                    "form": current["form"],
                    "fy": current.get("fy"),
                    "fp": fp,
                    "components": [],
                    "rule_version": RULE_VERSION,
                    "new_evidence_axis": NEW_EVIDENCE_AXIS,
                },
            )
            event["components"].append(comparison)

    stats["mapped_tickers_with_6k_financial_facts"] = len(tickers_with_rows)
    growth_events: list[dict[str, Any]] = []
    for event in events.values():
        best_by_component: dict[str, dict[str, Any]] = {}
        for component_row in event["components"]:
            component = component_row["component"]
            existing = best_by_component.get(component)
            if existing is None or float(component_row["component_score"] or 0.0) > float(
                existing["component_score"] or 0.0
            ):
                best_by_component[component] = component_row
        best_components = sorted(best_by_component.values(), key=lambda item: item["component"])
        passed_components = [item for item in best_components if item.get("passed")]
        growth_values = [
            float(item["growth"])
            for item in passed_components
            if item.get("growth") is not None
        ]
        score = sum(float(item.get("component_score") or 0.0) for item in passed_components)
        if any(item.get("component") in CORE_PROFIT_COMPONENTS for item in passed_components):
            score += 0.50
        if any(item.get("component") in TOPLINE_COMPONENTS for item in passed_components):
            score += 0.25
        topline_pass_count = sum(
            1 for item in passed_components if item["component"] in TOPLINE_COMPONENTS
        )
        core_profit_pass_count = sum(
            1 for item in passed_components if item["component"] in CORE_PROFIT_COMPONENTS
        )
        gate_passed = (
            len(passed_components) >= 2
            and topline_pass_count >= 1
            and core_profit_pass_count >= 1
        )
        enriched = {
            **event,
            "components": best_components,
            "passed_components": passed_components,
            "passed_component_count": len(passed_components),
            "topline_pass_count": topline_pass_count,
            "core_profit_pass_count": core_profit_pass_count,
            "average_passed_growth": round_float(
                sum(growth_values) / len(growth_values) if growth_values else None,
                6,
            ),
            "companyfacts_growth_score": round_float(score, 6),
            "growth_gate_passed": gate_passed,
        }
        if gate_passed:
            growth_events.append(enriched)

    growth_events.sort(
        key=lambda item: (
            item["filed_date"],
            str(item["ticker"]),
            str(item["accession"]),
        )
    )
    stats["growth_gate_event_rows"] = len(growth_events)
    stats["growth_gate_ticker_count"] = len({event["ticker"] for event in growth_events})
    stats["growth_gate_events_by_ticker"] = Counter(event["ticker"] for event in growth_events)
    return growth_events, stats


def next_trading_index_after(rows: list[dict[str, Any]], observed: date) -> tuple[int, str] | None:
    for idx, row in enumerate(rows):
        row_date = parse_date(row.get("Date"))
        if row_date is not None and row_date > observed:
            return idx, row_date.isoformat()
    return None


def candidate_from_event(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    cfg: dict[str, str],
    event: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    ticker = str(event.get("ticker") or "").upper()
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    filed = parse_date(event.get("filed_date"))
    if filed is None:
        return None, "missing_filed_date"
    next_idx = next_trading_index_after(rows, filed)
    if next_idx is None:
        return None, "missing_next_trading_day_after_filing"
    idx, signal_date = next_idx
    if signal_date < cfg["start"] or signal_date > cfg["end"]:
        return None, "signal_date_outside_window"
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None:
        return None, "missing_benchmark_day"
    close = value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None, "price_gate"
    adv20 = avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None, "liquidity_gate"
    signal_ret = daily_return(rows, idx)
    spy_signal_ret = daily_return(spy_rows, spy_idx)
    qqq_signal_ret = daily_return(qqq_rows, qqq_idx)
    if signal_ret is None or spy_signal_ret is None or qqq_signal_ret is None:
        return None, "missing_signal_return"
    if signal_ret < MIN_SIGNAL_RETURN or signal_ret > MAX_SIGNAL_RETURN:
        return None, "signal_return_gate"
    ret20 = ret(rows, idx, 20)
    spy_ret20 = ret(spy_rows, spy_idx, 20)
    ret60 = ret(rows, idx, 60)
    spy_ret60 = ret(spy_rows, spy_idx, 60)
    if ret20 is None or spy_ret20 is None or ret60 is None or spy_ret60 is None:
        return None, "missing_relative_return"
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None, "ret20_excess_spy_gate"
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None, "ret60_excess_spy_gate"
    close_loc = close_location(rows[idx])
    if close_loc is None or close_loc < MIN_CLOSE_LOCATION:
        return None, "close_location_gate"
    vol20 = realized_vol(rows, idx)
    if vol20 is None or vol20 > MAX_REALIZED_VOL_20D:
        return None, "realized_vol_gate"
    vol_ratio = volume_ratio(rows, idx)
    if (
        vol_ratio is None
        or vol_ratio < MIN_VOLUME_RATIO_20D
        or vol_ratio > MAX_VOLUME_RATIO_20D
    ):
        return None, "volume_ratio_gate"

    price_confirmation_score = (
        max(signal_ret - MIN_SIGNAL_RETURN, 0.0) * 3.0
        + max(ret20_excess_spy, 0.0) * 2.0
        + max(ret60_excess_spy, 0.0)
        + min(math.log10(max(adv20 / MIN_AVG_DOLLAR_VOLUME_20D, 1.0)), 2.0) * 0.10
        + close_loc * 0.10
    )
    candidate_score = float(event.get("companyfacts_growth_score") or 0.0) + price_confirmation_score
    return (
        {
            **event,
            "date": signal_date,
            "signal_date": signal_date,
            "filed_to_signal_trading_delay": 1,
            "candidate_source": STEM,
            "candidate_score": round_float(candidate_score, 6),
            "price_confirmation_score": round_float(price_confirmation_score, 6),
            "candidate_close": round_float(close, 4),
            "candidate_avg_dollar_volume_20d": round_float(adv20, 2),
            "candidate_signal_return": round_float(signal_ret, 6),
            "spy_signal_return": round_float(spy_signal_ret, 6),
            "qqq_signal_return": round_float(qqq_signal_ret, 6),
            "candidate_relative_vs_spy": round_float(signal_ret - spy_signal_ret, 6),
            "candidate_relative_vs_qqq": round_float(signal_ret - qqq_signal_ret, 6),
            "candidate_ret20_excess_spy": round_float(ret20_excess_spy, 6),
            "candidate_ret60_excess_spy": round_float(ret60_excess_spy, 6),
            "candidate_close_location": round_float(close_loc, 6),
            "candidate_realized_vol_20d": round_float(vol20, 6),
            "candidate_volume_ratio_20d": round_float(vol_ratio, 6),
        },
        "passed",
    )


def candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    events: list[dict[str, Any]],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    indices = {ticker: shadow._row_index(rows) for ticker, rows in snapshot.items()}
    entries_by_date = shadow._baseline_entries(before_result)
    candidates: list[dict[str, Any]] = []
    reject_reasons: Counter[str] = Counter()
    for event in events:
        candidate, reason = candidate_from_event(
            snapshot=snapshot,
            indices=indices,
            cfg=cfg,
            event=event,
        )
        if candidate is None:
            reject_reasons[reason] += 1
            continue
        ab_entries = entries_by_date.get(candidate["date"], [])
        candidate["same_day_ab_entry_count"] = len(ab_entries)
        candidate["same_day_ab_overlap"] = bool(ab_entries)
        candidate["same_ticker_ab_overlap"] = any(
            trade.get("ticker") == candidate["ticker"] for trade in ab_entries
        )
        candidates.append(candidate)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("companyfacts_growth_score") or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
            row["accession"],
        )
    )
    return candidates, reject_reasons


def select_paper_trades(
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
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
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


def gate4_result(
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

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_private_replay_lead_not_promoted_sec_6k_companyfacts_structured_growth"
            if passed
            else "rejected_sec_6k_companyfacts_structured_growth_candidate_pool"
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
        "minimum_core_survival_rate": round_float(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def build_payload() -> dict[str, Any]:
    configure_sleeve_globals()
    timestamp = utc_now()
    gate2_open_positions = sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    growth_events, event_surface = build_event_surface()
    eligible_tickers = {event["ticker"] for event in growth_events}
    universe = sorted(get_universe())

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    candidate_reject_reasons_by_window: "OrderedDict[str, dict[str, int]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in WINDOWS.items():
        print(f"[{label}] core baseline and 6-K Companyfacts replay")
        before_result = shadow._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = load_window_snapshot(cfg=cfg, eligible_tickers=eligible_tickers)
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "eligible_6k_growth_ticker_count": len(set(snapshot).intersection(eligible_tickers)),
            "source": repo_rel(WAREHOUSE),
        }
        candidates, reject_reasons = candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            events=growth_events,
            before_result=before_result,
        )
        selected_trades, filtered_candidates = select_paper_trades(
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
        candidate_reject_reasons_by_window[label] = dict(reject_reasons)
        raw_candidate_counts[label] = len(candidates)
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
    gate4 = gate4_result(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "observed_only" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    rejection_reason = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    post_run_reflection = {
        "why_result_happened": (
            "The form-scoped 6-K Companyfacts surface exists, but the fixed "
            "same-accession revenue plus profitability rule and liquid price "
            "confirmation collapsed to only five target trades across two "
            "windows. The late_strong losses overwhelmed the small mid_weak "
            "gain, old_thin produced zero selected trades, and all positive "
            "PnL came from one ticker/trade cluster, so the result failed both "
            "edge and sample/concentration gates."
        ),
        "realized_failure_mode": (
            "companyfacts_source_saturation_plus_thin_6k_fact_coverage"
            if not gate4["passed"]
            else "private_replay_positive_only"
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry adjacent 6-K Companyfacts tags, same-accession growth "
            "thresholds, filed-date delay, volume/liquidity guards, relative "
            "price confirmation gates, top-N, hold days, cooldown, or notional "
            "on these frozen windows. This would be another saturated "
            "Companyfacts-ratio candidate-pool retune."
        ),
        "new_evidence_required": (
            "A valid reopen needs historical 6-K filing text cache population, a new "
            "machine-checkable 6-K field unavailable in this Companyfacts "
            "surface, or mature forward replacement-value rows that prove this "
            "specific form-scoped growth signal adds allocation value."
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "candidate_pool_private_replay_scout",
        "implementation_mode": "private_replay_scout_no_shared_helper",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "causal_components": [
            "form-scoped Companyfacts fact surface",
            "same-accession year-over-year financial growth gate",
            "one-trading-day filed-date delay",
            "liquid relative price confirmation",
            "next-open 10-day paper replay",
            "accepted core baseline overlay comparison",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high_source_saturation_but_new_evidence_axis_declared",
        "new_evidence_type": "form_scoped_sec_companyfacts_6k_xbrl_growth_surface",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "experiment-owned private replay overlay"
            ),
            "windows": WINDOWS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "companyfacts_source": repo_rel(COMPANYFACTS_DIR),
            "candidate_ohlcv_source": repo_rel(WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "SEC Companyfacts rows provide filed date but not accepted_at, "
                "so signal date is conservatively delayed to the first trading "
                "day strictly after filed date. Paper entry is the next open "
                "after that signal day; exit is close 10 trading days after "
                "the signal with the existing sleeve cost/slippage model."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "forms": sorted(SIX_K_FORMS),
            "component_growth_thresholds": COMPONENT_GROWTH_THRESHOLDS,
            "required_topline_component_passes": 1,
            "required_core_profit_component_passes": 1,
            "required_total_component_passes": 2,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate_result": (
                    "Allowed only with novelty and saturated-source overrides. "
                    "Companyfacts ratio family is saturated, but this run uses "
                    "a machine-checkable form-scoped 6-K/6-KA XBRL surface that "
                    "replaces missing historical filing text."
                ),
                "exp-20260625-011": (
                    "Measurement repair found 8010 6-K/6-KA historical events "
                    "but zero historical filing text rows; current run avoids "
                    "text and uses Companyfacts fact rows."
                ),
                "exp-20260625-006": (
                    "Companyfacts quality forward attribution rejected; current "
                    "run is not a generic field threshold sweep."
                ),
                "exp-20260622-016": (
                    "Structured 6-K financial-growth helper was blocked by zero "
                    "historical 6-K text rows."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Gate 4 on canonical windows: aggregate EV and PnL positive, no "
                "window EV/PnL regression, at least 20 trades across all 3 "
                "windows, survival >=5%, drawdown drift <=0.5pp, concentration "
                "pass. Positive private replay is only a lead, not accepted alpha."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{repo_rel(OUT_JSON)}#before_metrics",
            "canonical_baseline_result_file": repo_rel(BASELINE_RESULT),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "event_surface": event_surface,
            "runtime_fields": [
                "Companyfacts facts.*.*.units rows with form",
                "Companyfacts filed date",
                "Companyfacts accn accession",
                "Companyfacts end date",
                "Companyfacts val numeric value",
                "SEC company tickers CIK to ticker map",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "QQQ daily OHLCV",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "pit_notes": (
                "Companyfacts provides filed date but not accepted_at. This "
                "private replay delays every candidate to the first trading day "
                "strictly after filed_date before applying price gates."
            ),
            "passed": bool(growth_events) and gate2_open_positions["passed"],
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round_float(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The 6-K "
                "Companyfacts source is an additive private replay paper overlay."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "candidate_reject_reasons_by_window": candidate_reject_reasons_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The private 6-K Companyfacts structured-growth replay cleared Gate "
            "4 as an observed-only lead. It is not accepted alpha because no "
            "shared helper or daily default-off parity surface was promoted."
            if gate4["passed"]
            else (
                "The private 6-K Companyfacts structured-growth candidate pool "
                "did not clear Gate 4. Do not promote it or retry adjacent "
                "Companyfacts 6-K tag/threshold variants on the same frozen "
                "windows without a materially new evidence axis."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, avoid adjacent Companyfacts 6-K threshold/tag retunes. "
            "A valid retry needs historical filing text backfill, a new "
            "machine-checkable 6-K field unavailable here, or mature forward "
            "replacement-value rows. If positive, next step is a shared "
            "default-off helper plus daily snapshot before acceptance."
        ),
        "post_run_reflection": post_run_reflection,
        "changed_files": [
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
    }


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    surface = payload["gate2"]["event_surface"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 6-K Companyfacts Structured Growth Scout",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "- Lane: `alpha_search`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Evidence Surface",
            "",
            f"- Raw 6-K/6-KA financial fact rows: `{surface['raw_6k_financial_fact_rows']}`",
            f"- Same-accession comparisons: `{surface['same_accession_comparisons']}`",
            f"- Growth-gate events: `{surface['growth_gate_event_rows']}`",
            f"- Growth-gate tickers: `{surface['growth_gate_ticker_count']}`",
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            "Private replay only. No shared helper, run adapter, backtester adapter, daily snapshot, production watchlist, ranking, sizing, exit, paper order, or live order behavior changed.",
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": LANE,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "growth_gate_event_rows": payload["gate2"]["event_surface"]["growth_gate_event_rows"],
            "growth_gate_ticker_count": payload["gate2"]["event_surface"][
                "growth_gate_ticker_count"
            ],
            "raw_6k_financial_fact_rows": payload["gate2"]["event_surface"][
                "raw_6k_financial_fact_rows"
            ],
            "open_positions": payload["gate2"]["open_positions"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "production_impact": PRODUCTION_IMPACT,
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "anti_js": "No JavaScript was used.",
    }


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "anti_js": payload["anti_js"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG_JSONL, log_row)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "gate4_passed": payload["gate4"]["passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "delta_metrics": payload["delta_metrics"],
        "gate2": log_row["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["interpretation"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [
                {"label": label, **window} for label, window in WINDOWS.items()
            ],
            "acceptance_rule": payload["pre_run_questions"]["4_success_failure_standard"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": log_row["aggregate_expected_value_delta"],
            "aggregate_strategy_total_pnl_delta": log_row[
                "aggregate_strategy_total_pnl_delta"
            ],
            "gate1": payload["gate1"],
            "gate2": log_row["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": PRODUCTION_IMPACT,
            "reproduction_commands": payload["reproduction_commands"],
            "changed_files": payload["changed_files"],
            "anti_js": payload["anti_js"],
        },
    )
    manifest = build_manifest(payload, log_row)
    write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log_row(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
