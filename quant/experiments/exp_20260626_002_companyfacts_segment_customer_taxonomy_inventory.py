"""exp-20260626-002: Companyfacts segment/customer taxonomy inventory.

Measurement repair only. This builds a replayable inventory of SEC
Companyfacts tags that look like segment, customer, counterparty, backlog, or
contract-economics provenance across the broad liquid warehouse universe.

No strategy, ranking, sizing, exits, paper orders, live orders, watchlist, LLM,
or daily production behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-002"
OWNER = "alpha-explore"
SLUG = "companyfacts_segment_customer_taxonomy_inventory"
RUNNER = f"quant/experiments/exp_20260626_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
COMPANYFACTS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_002_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha-enabling measurement repair: a future segment/customer/counterparty "
    "provenance candidate pool may be a valid non-frozen Companyfacts axis, "
    "but it is not testable until the local SEC Companyfacts cache has a PIT "
    "taxonomy/tag inventory for segment/customer fields across the broad "
    "liquid warehouse universe."
)
ALPHA_HYPOTHESIS = (
    "A future alpha may use richer PIT segment mix, customer concentration, "
    "or contract-economics provenance to avoid fragile demand and favor "
    "durable growth, but only if the local Companyfacts cache exposes enough "
    "machine-checkable fields across tickers and windows."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "companyfacts_segment_customer_data_edge"
TRIAL_FAMILY = "companyfacts_segment_customer_taxonomy_inventory"
TRIAL_VARIANT_ID = "broad_liquid_companyfacts_tag_coverage_v1"
CHANGED_VARIABLE = "sec_companyfacts_segment_customer_taxonomy_inventory_v1"
NEW_EVIDENCE_TYPE = "machine_checkable_companyfacts_taxonomy_tag_inventory"
NEW_EVIDENCE_AXIS = (
    "Machine-checkable data-edge construction for extension/dei/us-gaap tags "
    "whose tag/label/description indicate segment, customer, counterparty, "
    "concentration, product, geographic, backlog, or contract provenance; no "
    "candidate-pool threshold, ranking, top-N, hold-day, or notional policy is "
    "tested."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260617-012",
    "exp-20260617-020",
    "exp-20260617-022",
    "exp-20260622-004",
    "exp-20260625-005",
]
CAUSAL_COMPONENTS = [
    "broad liquid warehouse CIK universe",
    "SEC Companyfacts taxonomy/tag keyword inventory",
    "generic customer-contract revenue separation",
    "standard-window filed-date coverage counts",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_002_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

WINDOW_FALLBACKS = [
    {"label": "old_thin", "start": "2019-01-01", "end": "2020-12-31"},
    {"label": "mid_weak", "start": "2021-07-01", "end": "2022-06-30"},
    {"label": "late_strong", "start": "2023-10-01", "end": "2024-03-31"},
]
KEYWORD_CATEGORIES: dict[str, tuple[str, ...]] = {
    "segment": (
        "segment",
        "reportable segment",
        "operating segment",
        "business unit",
        "division",
    ),
    "customer": (
        "customer",
        "customers",
        "client",
        "subscriber",
        "merchant",
        "tenant",
        "end user",
    ),
    "concentration": (
        "concentration",
        "concentrated",
        "dependence",
        "dependency",
        "reliance",
        "major customer",
    ),
    "counterparty_contract": (
        "counterparty",
        "performance obligation",
        "noncancelable",
        "non-cancelable",
        "purchase commitment",
        "customer advance",
        "contract asset",
        "contract liability",
    ),
    "geographic": (
        "geographic revenue",
        "geographical revenue",
        "revenue by geographic",
        "revenue by geography",
        "geographic area",
        "geographical area",
        "domestic revenue",
        "foreign revenue",
        "international revenue",
        "sales by geographic",
        "long-lived assets by geographic",
    ),
    "product_service": (
        "product revenue",
        "products revenue",
        "service revenue",
        "services revenue",
        "subscription revenue",
        "software revenue",
        "product sales",
        "service sales",
        "sales by product",
        "revenue by product",
        "revenue by service",
    ),
    "backlog_orders": (
        "backlog",
        "booking",
        "bookings",
        "order",
        "orders",
        "remaining performance obligation",
    ),
}
GENERIC_TAG_PATTERNS = (
    re.compile(r"revenuefromcontractwithcustomer", re.IGNORECASE),
    re.compile(r"contractwithcustomer(asset|liabilit|refund|receivable)", re.IGNORECASE),
    re.compile(r"accountsreceivable", re.IGNORECASE),
    re.compile(r"unearnedrevenue", re.IGNORECASE),
    re.compile(r"deferredrevenue", re.IGNORECASE),
)
LOW_INFORMATION_TAG_PATTERNS = (
    re.compile(r"numberofreportablesegments", re.IGNORECASE),
    re.compile(r"numberofoperatingsegments", re.IGNORECASE),
    re.compile(r"numberofreportingunits", re.IGNORECASE),
    re.compile(r"reportablesegments?member", re.IGNORECASE),
    re.compile(r"segmentreporting", re.IGNORECASE),
    re.compile(r"operatingsegments?table", re.IGNORECASE),
    re.compile(r"scheduleof.*segments?", re.IGNORECASE),
    re.compile(r"operatingleases?", re.IGNORECASE),
    re.compile(r"lease", re.IGNORECASE),
    re.compile(r"incometax|taxexpense|taxrate|taxeffect", re.IGNORECASE),
    re.compile(r"receivable", re.IGNORECASE),
    re.compile(r"productwarranty|warranty", re.IGNORECASE),
    re.compile(r"healthcarecosttrend", re.IGNORECASE),
    re.compile(r"professionalfees", re.IGNORECASE),
    re.compile(r"accruedmarketing", re.IGNORECASE),
    re.compile(r"cashcashequivalents", re.IGNORECASE),
    re.compile(r"definedbenefit", re.IGNORECASE),
    re.compile(r"derivativeinstrument", re.IGNORECASE),
)
LOW_INFORMATION_TEXT_PATTERNS = (
    re.compile(r"number of reportable segments", re.IGNORECASE),
    re.compile(r"number of operating segments", re.IGNORECASE),
    re.compile(r"number of reporting units", re.IGNORECASE),
    re.compile(r"segment reporting", re.IGNORECASE),
    re.compile(r"schedule of .*segments?", re.IGNORECASE),
    re.compile(r"operating leases?", re.IGNORECASE),
    re.compile(r"income tax|tax rate|tax effect", re.IGNORECASE),
    re.compile(r"accounts? receivable", re.IGNORECASE),
    re.compile(r"product warranty|health care cost trend", re.IGNORECASE),
)
HIGH_SIGNAL_TEXT_PATTERNS = (
    re.compile(r"major customer", re.IGNORECASE),
    re.compile(r"customer concentration", re.IGNORECASE),
    re.compile(r"concentration risk", re.IGNORECASE),
    re.compile(r"remaining performance obligation", re.IGNORECASE),
    re.compile(r"\bbacklog\b", re.IGNORECASE),
    re.compile(r"\bbookings?\b", re.IGNORECASE),
    re.compile(r"purchase commitment|purchase obligation", re.IGNORECASE),
    re.compile(r"segment (revenue|profit|income|sales|margin)", re.IGNORECASE),
    re.compile(r"(revenue|sales|profit|income) .*segment", re.IGNORECASE),
    re.compile(r"(geographic|geographical) (revenue|sales)", re.IGNORECASE),
    re.compile(r"(product|service|subscription|software) (revenue|sales)", re.IGNORECASE),
)
CUSTOMER_REVENUE_TEXT_PATTERNS = (
    re.compile(r"revenue from contract with customer", re.IGNORECASE),
    re.compile(r"contract with customer", re.IGNORECASE),
)
MAX_TAG_SUMMARIES = 240
MAX_TAG_SAMPLES = 5
MAX_SAMPLE_TICKERS = 12


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(value)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
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
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if math.isfinite(number) else None


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def cik_to_filename(cik: Any) -> str | None:
    if cik is None:
        return None
    digits = re.sub(r"\D+", "", str(cik))
    if not digits:
        return None
    return f"CIK{int(digits):010d}.json"


def compact_text(value: Any, limit: int = 180) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def baseline_metrics() -> dict[str, Any]:
    payload = load_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload.get("windows"), list) else []
    by_label: dict[str, dict[str, Any]] = {}
    for row in windows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or f"window_{len(by_label) + 1}")
        by_label[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "expected_value_score": round_float(row.get("expected_value_score")),
            "sharpe_daily": round_float(row.get("sharpe_daily")),
            "total_pnl": round_float(row.get("total_pnl")),
            "strategy_total_return_pct": round_float(row.get("strategy_total_return_pct")),
            "max_drawdown_pct": round_float(row.get("max_drawdown_pct")),
            "trades": row.get("trades") or row.get("trade_count"),
        }
    return {
        "path": repo_rel(BASELINE_RESULT),
        "exists": BASELINE_RESULT.exists(),
        "aggregate_expected_value_score": round_float(
            payload.get("aggregate_expected_value_score")
            or payload.get("expected_value_score")
            or payload.get("aggregate", {}).get("expected_value_score")
        ),
        "aggregate_total_pnl": round_float(
            payload.get("aggregate_total_pnl")
            or payload.get("total_pnl")
            or payload.get("aggregate", {}).get("total_pnl")
        ),
        "windows": by_label,
    }


def standard_windows() -> list[dict[str, str]]:
    metrics = baseline_metrics()
    windows = []
    for label, row in metrics.get("windows", {}).items():
        if row.get("start") and row.get("end"):
            windows.append({"label": label, "start": row["start"], "end": row["end"]})
    return windows or WINDOW_FALLBACKS


def load_universe() -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if WAREHOUSE_DB.exists():
        query = """
            select u.ticker, u.cik
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
              and u.cik is not null
            order by u.ticker
        """
        try:
            with sqlite3.connect(WAREHOUSE_DB) as conn:
                rows = [
                    {"ticker": str(ticker), "cik": cik_to_filename(cik), "raw_cik": cik}
                    for ticker, cik in conn.execute(query)
                    if cik_to_filename(cik)
                ]
            if rows:
                return rows, warnings
            warnings.append("warehouse_query_returned_zero_rows")
        except sqlite3.Error as exc:
            warnings.append(f"warehouse_query_failed:{type(exc).__name__}:{exc}")
    else:
        warnings.append("warehouse_db_missing")

    fallback_rows = []
    for path in sorted(COMPANYFACTS_DIR.glob("CIK*.json")):
        fallback_rows.append({"ticker": path.stem, "cik": path.name, "raw_cik": path.stem})
    if fallback_rows:
        warnings.append("used_companyfacts_file_fallback_universe")
    return fallback_rows, warnings


def categories_for_tag(taxonomy: str, tag: str, fact: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            taxonomy,
            tag,
            str(fact.get("label") or ""),
            str(fact.get("description") or ""),
        ]
    ).lower()
    categories = []
    for category, keywords in KEYWORD_CATEGORIES.items():
        if any(keyword.lower() in text for keyword in keywords):
            categories.append(category)
    return categories


def is_generic_customer_contract_tag(tag: str, fact: dict[str, Any]) -> bool:
    if any(pattern.search(tag) for pattern in GENERIC_TAG_PATTERNS):
        return True
    text = " ".join([str(fact.get("label") or ""), str(fact.get("description") or "")])
    return any(pattern.search(text) for pattern in CUSTOMER_REVENUE_TEXT_PATTERNS)


def is_low_information_provenance_tag(tag: str, fact: dict[str, Any]) -> bool:
    if any(pattern.search(tag) for pattern in LOW_INFORMATION_TAG_PATTERNS):
        return True
    text = " ".join([str(fact.get("label") or ""), str(fact.get("description") or "")])
    return any(pattern.search(text) for pattern in LOW_INFORMATION_TEXT_PATTERNS)


def is_high_signal_provenance_tag(
    tag: str,
    fact: dict[str, Any],
    generic_contract: bool,
    low_information: bool,
) -> bool:
    if generic_contract or low_information:
        return False
    text = " ".join([tag, str(fact.get("label") or ""), str(fact.get("description") or "")])
    return any(pattern.search(text) for pattern in HIGH_SIGNAL_TEXT_PATTERNS)


def fact_units(fact: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    units = fact.get("units")
    if not isinstance(units, dict):
        return rows
    for unit, unit_rows in units.items():
        if not isinstance(unit_rows, list):
            continue
        for row in unit_rows:
            if isinstance(row, dict):
                rows.append((str(unit), row))
    return rows


def window_label_for_filed(filed: date | None, windows: list[dict[str, str]]) -> str | None:
    if filed is None:
        return None
    for window in windows:
        start = parse_date(window["start"])
        end = parse_date(window["end"])
        if start and end and start <= filed <= end:
            return str(window["label"])
    return None


def new_tag_bucket(
    taxonomy: str,
    tag: str,
    fact: dict[str, Any],
    categories: list[str],
    generic_contract: bool,
    low_information: bool,
    high_signal: bool,
) -> dict[str, Any]:
    return {
        "taxonomy": taxonomy,
        "tag": tag,
        "label": compact_text(fact.get("label"), 220),
        "description": compact_text(fact.get("description"), 260),
        "categories": set(categories),
        "generic_customer_contract": generic_contract,
        "low_information_provenance": low_information,
        "high_signal_provenance": high_signal,
        "row_count": 0,
        "filed_row_count": 0,
        "ticker_set": set(),
        "forms": Counter(),
        "units": Counter(),
        "filed_dates": [],
        "window_counts": Counter(),
        "sample_tickers": [],
        "sample_rows": [],
    }


def add_sample(bucket: dict[str, Any], ticker: str, unit: str, row: dict[str, Any]) -> None:
    if ticker not in bucket["sample_tickers"] and len(bucket["sample_tickers"]) < MAX_SAMPLE_TICKERS:
        bucket["sample_tickers"].append(ticker)
    if len(bucket["sample_rows"]) >= MAX_TAG_SAMPLES:
        return
    bucket["sample_rows"].append(
        {
            "ticker": ticker,
            "filed": row.get("filed"),
            "form": row.get("form"),
            "fy": row.get("fy"),
            "fp": row.get("fp"),
            "start": row.get("start"),
            "end": row.get("end"),
            "unit": unit,
            "val": round_float(row.get("val"), 4),
            "accn": row.get("accn"),
        }
    )


def scan_companyfacts() -> dict[str, Any]:
    universe, universe_warnings = load_universe()
    windows = standard_windows()
    tag_buckets: dict[str, dict[str, Any]] = {}
    total_fact_tags_scanned = 0
    files_present = 0
    files_missing = 0
    files_decode_error = 0
    missing_files_sample: list[str] = []
    decode_error_sample: list[str] = []
    tickers_with_any_match: set[str] = set()
    specific_tickers: set[str] = set()
    category_row_counts: Counter[str] = Counter()
    category_tag_keys: dict[str, set[str]] = defaultdict(set)
    taxonomy_counts: Counter[str] = Counter()
    all_window_counts: Counter[str] = Counter()
    specific_window_counts: Counter[str] = Counter()
    generic_row_count = 0
    low_information_row_count = 0
    specific_row_count = 0
    high_signal_row_count = 0
    high_signal_tickers: set[str] = set()
    high_signal_window_counts: Counter[str] = Counter()

    for entry in universe:
        ticker = str(entry["ticker"])
        cik_file = entry["cik"]
        path = COMPANYFACTS_DIR / cik_file
        if not path.exists():
            files_missing += 1
            if len(missing_files_sample) < 20:
                missing_files_sample.append(f"{ticker}:{cik_file}")
            continue
        payload = load_json(path)
        if not isinstance(payload, dict):
            files_decode_error += 1
            if len(decode_error_sample) < 20:
                decode_error_sample.append(f"{ticker}:{cik_file}")
            continue
        files_present += 1
        facts = payload.get("facts")
        if not isinstance(facts, dict):
            continue
        for taxonomy, tag_map in facts.items():
            if not isinstance(tag_map, dict):
                continue
            taxonomy = str(taxonomy)
            for tag, fact in tag_map.items():
                if not isinstance(fact, dict):
                    continue
                total_fact_tags_scanned += 1
                tag = str(tag)
                categories = categories_for_tag(taxonomy, tag, fact)
                if not categories:
                    continue
                generic_contract = is_generic_customer_contract_tag(tag, fact)
                low_information = is_low_information_provenance_tag(tag, fact)
                high_signal = is_high_signal_provenance_tag(
                    tag,
                    fact,
                    generic_contract,
                    low_information,
                )
                tag_key = f"{taxonomy}:{tag}"
                bucket = tag_buckets.get(tag_key)
                if bucket is None:
                    bucket = new_tag_bucket(
                        taxonomy,
                        tag,
                        fact,
                        categories,
                        generic_contract,
                        low_information,
                        high_signal,
                    )
                    tag_buckets[tag_key] = bucket
                else:
                    bucket["categories"].update(categories)
                    bucket["generic_customer_contract"] = (
                        bucket["generic_customer_contract"] or generic_contract
                    )
                    bucket["low_information_provenance"] = (
                        bucket["low_information_provenance"] or low_information
                    )
                    bucket["high_signal_provenance"] = (
                        bucket["high_signal_provenance"] or high_signal
                    )
                unit_rows = fact_units(fact)
                taxonomy_counts[taxonomy] += len(unit_rows)
                for unit, row in unit_rows:
                    bucket["row_count"] += 1
                    bucket["ticker_set"].add(ticker)
                    filed = parse_date(row.get("filed"))
                    if filed:
                        bucket["filed_row_count"] += 1
                        bucket["filed_dates"].append(filed.isoformat())
                    if row.get("form"):
                        bucket["forms"][str(row.get("form"))] += 1
                    bucket["units"][unit] += 1
                    for category in categories:
                        category_row_counts[category] += 1
                        category_tag_keys[category].add(tag_key)
                    label = window_label_for_filed(filed, windows)
                    if label:
                        bucket["window_counts"][label] += 1
                        all_window_counts[label] += 1
                    add_sample(bucket, ticker, unit, row)
                    tickers_with_any_match.add(ticker)
                    if generic_contract:
                        generic_row_count += 1
                    elif low_information:
                        low_information_row_count += 1
                    else:
                        specific_row_count += 1
                        specific_tickers.add(ticker)
                        if label:
                            specific_window_counts[label] += 1
                        if high_signal:
                            high_signal_row_count += 1
                            high_signal_tickers.add(ticker)
                            if label:
                                high_signal_window_counts[label] += 1

    converted_tags = []
    specific_tag_count = 0
    generic_tag_count = 0
    low_information_tag_count = 0
    high_signal_tag_count = 0
    for key, bucket in tag_buckets.items():
        ticker_count = len(bucket["ticker_set"])
        if bucket["generic_customer_contract"]:
            generic_tag_count += 1
        elif bucket["low_information_provenance"]:
            low_information_tag_count += 1
        else:
            specific_tag_count += 1
            if bucket["high_signal_provenance"]:
                high_signal_tag_count += 1
        converted_tags.append(
            {
                "key": key,
                "taxonomy": bucket["taxonomy"],
                "tag": bucket["tag"],
                "label": bucket["label"],
                "description": bucket["description"],
                "categories": sorted(bucket["categories"]),
                "generic_customer_contract": bool(bucket["generic_customer_contract"]),
                "low_information_provenance": bool(bucket["low_information_provenance"]),
                "high_signal_provenance": bool(bucket["high_signal_provenance"]),
                "row_count": bucket["row_count"],
                "filed_row_count": bucket["filed_row_count"],
                "ticker_count": ticker_count,
                "sample_tickers": bucket["sample_tickers"],
                "forms": dict(bucket["forms"].most_common(10)),
                "units": dict(bucket["units"].most_common(10)),
                "filed_min": min(bucket["filed_dates"]) if bucket["filed_dates"] else None,
                "filed_max": max(bucket["filed_dates"]) if bucket["filed_dates"] else None,
                "window_counts": dict(bucket["window_counts"]),
                "sample_rows": bucket["sample_rows"],
            }
        )
    converted_tags.sort(
        key=lambda item: (
            item["generic_customer_contract"],
            item["low_information_provenance"],
            not item["high_signal_provenance"],
            -int(item["ticker_count"]),
            -int(item["row_count"]),
            item["key"],
        )
    )

    window_labels = [str(window["label"]) for window in windows]
    specific_min_window_rows = (
        min(specific_window_counts.get(label, 0) for label in window_labels)
        if window_labels
        else 0
    )
    high_signal_min_window_rows = (
        min(high_signal_window_counts.get(label, 0) for label in window_labels)
        if window_labels
        else 0
    )
    ready_for_future_alpha = (
        high_signal_tag_count >= 5
        and len(high_signal_tickers) >= 30
        and high_signal_min_window_rows >= 25
    )
    if ready_for_future_alpha:
        readiness_reason = (
            "conditional_data_edge_ready: high-signal provenance-like tags have "
            "enough ticker/window coverage for one future strictly PIT alpha scout."
        )
    elif high_signal_tag_count == 0:
        readiness_reason = "not_ready: no high-signal provenance-like Companyfacts tags were found."
    elif len(high_signal_tickers) < 30:
        readiness_reason = "not_ready: high-signal provenance-like coverage is too ticker-sparse."
    else:
        readiness_reason = "not_ready: standard-window high-signal filed rows are too sparse."

    return {
        "universe": {
            "source": repo_rel(WAREHOUSE_DB) if WAREHOUSE_DB.exists() else repo_rel(COMPANYFACTS_DIR),
            "broad_liquid_cik_rows": len(universe),
            "warnings": universe_warnings,
        },
        "coverage": {
            "companyfacts_dir": repo_rel(COMPANYFACTS_DIR),
            "files_present": files_present,
            "files_missing": files_missing,
            "files_decode_error": files_decode_error,
            "missing_files_sample": missing_files_sample,
            "decode_error_sample": decode_error_sample,
            "total_fact_tags_scanned": total_fact_tags_scanned,
            "matched_tag_count": len(converted_tags),
            "specific_provenance_tag_count": specific_tag_count,
            "generic_customer_contract_tag_count": generic_tag_count,
            "low_information_provenance_tag_count": low_information_tag_count,
            "high_signal_provenance_tag_count": high_signal_tag_count,
            "matched_row_count": sum(int(item["row_count"]) for item in converted_tags),
            "specific_provenance_row_count": specific_row_count,
            "generic_customer_contract_row_count": generic_row_count,
            "low_information_provenance_row_count": low_information_row_count,
            "high_signal_provenance_row_count": high_signal_row_count,
            "tickers_with_any_match": len(tickers_with_any_match),
            "tickers_with_specific_provenance": len(specific_tickers),
            "tickers_with_high_signal_provenance": len(high_signal_tickers),
        },
        "windows": windows,
        "window_counts": {
            "all_matched_rows": {label: all_window_counts.get(label, 0) for label in window_labels},
            "specific_provenance_rows": {
                label: specific_window_counts.get(label, 0) for label in window_labels
            },
            "high_signal_provenance_rows": {
                label: high_signal_window_counts.get(label, 0) for label in window_labels
            },
        },
        "category_counts": {
            category: {
                "row_count": category_row_counts.get(category, 0),
                "tag_count": len(category_tag_keys.get(category, set())),
            }
            for category in sorted(KEYWORD_CATEGORIES)
        },
        "taxonomy_row_counts": dict(taxonomy_counts.most_common()),
        "tag_inventory_top": converted_tags[:MAX_TAG_SUMMARIES],
        "tag_inventory_truncated": len(converted_tags) > MAX_TAG_SUMMARIES,
        "candidate_surface_assessment": {
            "ready_for_future_alpha": ready_for_future_alpha,
            "readiness_reason": readiness_reason,
            "minimum_specific_rows_in_standard_window": specific_min_window_rows,
            "minimum_high_signal_rows_in_standard_window": high_signal_min_window_rows,
            "required_for_next_alpha": [
                "use filed date as PIT as-of boundary",
                "select one concrete provenance axis before candidate-pool testing",
                "do not sweep adjacent Companyfacts thresholds/top-N/hold days",
                "avoid treating generic revenue-from-contract tags as customer identity",
            ],
        },
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket_before = load_json(TICKET_JSON, {}) or {}
    scan = scan_companyfacts()
    coverage = scan["coverage"]
    gate2_passed = (
        scan["universe"]["broad_liquid_cik_rows"] > 0
        and coverage["files_present"] > 0
        and coverage["matched_tag_count"] > 0
    )
    gate2_reasons = []
    if scan["universe"]["broad_liquid_cik_rows"] <= 0:
        gate2_reasons.append("empty_broad_liquid_cik_universe")
    if coverage["files_present"] <= 0:
        gate2_reasons.append("no_companyfacts_files_present")
    if coverage["matched_tag_count"] <= 0:
        gate2_reasons.append("no_segment_customer_counterparty_tags_matched")
    gate4_passed = gate2_passed
    status = "accepted" if gate4_passed else "rejected"
    decision = (
        "accepted_measurement_repair_inventory"
        if gate4_passed
        else "rejected_measurement_repair_inventory"
    )
    readiness = scan["candidate_surface_assessment"]
    if readiness["ready_for_future_alpha"]:
        why = (
            "The run built a replayable Companyfacts taxonomy inventory and found "
            "non-generic provenance-like tags with enough cross-window coverage "
            "to justify one future PIT alpha scout. This is not an accepted alpha "
            "because no entry, ranking, sizing, or exit rule was tested."
        )
        next_step = (
            "Choose one concrete axis from tag_inventory_top, such as segment mix "
            "or backlog/order provenance, then reserve a shared-paper-first alpha "
            "with fixed PIT filed-date boundaries."
        )
    else:
        why = (
            "The run built the replayable Companyfacts taxonomy inventory, but "
            "the matched surface is not ready for a candidate-pool alpha under "
            f"the readiness rule: {readiness['readiness_reason']}"
        )
        next_step = (
            "Do not retune adjacent Companyfacts candidate pools; add parsed "
            "footnote identity/contract economics or materially more forward "
            "closed replacement rows before revisiting this source."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "owner": OWNER,
        "status": status,
        "accepted": gate4_passed,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "self_registered_measurement_repair_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": ticket_before.get("prediction")
        or {
            "success_probability": 0.55,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "no_structured_segment_customer_tags",
                "coverage_too_sparse",
                "fields_are_generic_revenue_not_provenance",
                "source_too_extension_specific",
            ],
            "confidence_reason": (
                "Novelty gate did not block measurement repair; playbook requires "
                "richer segment/customer/counterparty provenance before more "
                "Companyfacts candidate-pool tests."
            ),
            "recorded_at": timestamp,
        },
        "calibration": {
            "prediction_outcome": "accepted_measurement_repair" if gate4_passed else "blocked",
            "surprise_note": (
                "Novelty and source-saturation warnings were expected and honored "
                "by producing only a data-edge inventory, not an alpha rescan."
            ),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline_metrics(),
            "note": "Strategy baseline is unchanged; this measurement repair does not run before/after trades.",
        },
        "gate2": {
            "passed": gate2_passed,
            "required_fields_checked": [
                "ticker",
                "cik",
                "taxonomy",
                "tag",
                "label",
                "description",
                "units",
                "filed",
                "form",
                "end",
                "val",
            ],
            "failed_reasons": gate2_reasons,
            "inventory_summary": {
                "universe": scan["universe"],
                "coverage": coverage,
                "window_counts": scan["window_counts"],
                "category_counts": scan["category_counts"],
                "taxonomy_row_counts": scan["taxonomy_row_counts"],
                "candidate_surface_assessment": readiness,
            },
        },
        "gate3": {
            "passed": True,
            "signals_generated": coverage["matched_row_count"],
            "signals_survived": coverage["matched_row_count"],
            "survival_rate": 1.0 if coverage["matched_row_count"] else 0.0,
            "note": "Not a filtering experiment; row counts describe inventory observations only.",
        },
        "gate4": {
            "passed": gate4_passed,
            "decision_basis": "measurement_repair_artifact_completeness",
            "expected_value_score_before": None,
            "expected_value_score_after": None,
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "candidate_surface_assessment": readiness,
            "failed_reasons": gate2_reasons,
            "note": "No Gate 4 strategy metric improvement is required or claimed.",
        },
        "inventory": scan,
        "production_impact": {
            "changes_live_orders": False,
            "changes_trade_enabled": False,
            "changes_ranking": False,
            "changes_sizing": False,
            "changes_exits": False,
            "changes_watchlist": False,
            "changes_llm_decision_boundary": False,
            "summary": "No production behavior changed; this is an offline SEC taxonomy inventory.",
        },
        "live_realistic_execution_envelope": {
            "required": False,
            "reason": "No executable alpha, order, notional, or ranking policy was introduced.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not use this inventory as permission to sweep Companyfacts "
                "thresholds, top-N, hold days, freshness, liquidity guards, or "
                "generic revenue-from-contract/customer tags on frozen windows."
            ),
            "new_evidence_required": (
                "A valid next alpha needs one machine-checkable new evidence axis: "
                "parsed customer identity, contract duration/funding certainty, "
                "segment revenue/profit mix, a selected PIT tag surface with a new "
                "gate shape, or materially more closed forward rows."
            ),
            "next_step": next_step,
        },
        "related_files": [
            repo_rel(WAREHOUSE_DB),
            repo_rel(COMPANYFACTS_DIR),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": ALLOWED_WRITE_SCOPE,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "ticket_before": ticket_before,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "revision_manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "lean_quality_passed": gate4_passed,
        "anti_js": "No JavaScript was used.",
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    inventory_summary = payload["gate2"]["inventory_summary"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "owner": OWNER,
        "status": payload["status"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "gate1": payload["gate1"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "required_fields_checked": payload["gate2"]["required_fields_checked"],
            "failed_reasons": payload["gate2"]["failed_reasons"],
            "inventory_summary": inventory_summary,
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "source_summary": {
            "coverage": inventory_summary["coverage"],
            "candidate_surface_assessment": inventory_summary["candidate_surface_assessment"],
        },
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "production_impact": payload["production_impact"],
        "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "runner": payload["runner"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    coverage = payload["gate2"]["inventory_summary"]["coverage"]
    readiness = payload["gate4"]["candidate_surface_assessment"]
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts segment/customer taxonomy inventory",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Broad liquid CIK rows: `{payload['gate2']['inventory_summary']['universe']['broad_liquid_cik_rows']}`",
        f"- Companyfacts files present: `{coverage['files_present']}`",
        f"- Fact tags scanned: `{coverage['total_fact_tags_scanned']}`",
        f"- Matched tags: `{coverage['matched_tag_count']}`",
        f"- Specific provenance-like tags: `{coverage['specific_provenance_tag_count']}`",
        f"- Generic customer-contract tags: `{coverage['generic_customer_contract_tag_count']}`",
        f"- Low-information provenance tags: `{coverage['low_information_provenance_tag_count']}`",
        f"- High-signal provenance tags: `{coverage['high_signal_provenance_tag_count']}`",
        f"- Tickers with specific provenance: `{coverage['tickers_with_specific_provenance']}`",
        f"- Tickers with high-signal provenance: `{coverage['tickers_with_high_signal_provenance']}`",
        f"- Specific rows by window: `{payload['gate2']['inventory_summary']['window_counts']['specific_provenance_rows']}`",
        f"- High-signal rows by window: `{payload['gate2']['inventory_summary']['window_counts']['high_signal_provenance_rows']}`",
        f"- Future alpha surface ready: `{readiness['ready_for_future_alpha']}`",
        f"- Readiness reason: `{readiness['readiness_reason']}`",
        "",
        "## Interpretation",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduction",
        "",
        "```powershell",
        RUNNER_COMMAND,
        ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        "```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        WAREHOUSE_DB,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in paths},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload.get("ticket_before") or {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": utc_now(),
            "result": {
                "accepted": payload["accepted"],
                "accepted_alpha": False,
                "alpha_ready": False,
                "decision": payload["decision"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "runner": RUNNER,
                "gate4": payload["gate4"],
                "summary": payload["post_run_reflection"]["why_result_happened"],
            },
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "changed_files": payload["changed_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
        }
    )
    write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))
    update_ticket(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "coverage": payload["gate2"]["inventory_summary"]["coverage"],
                "candidate_surface_assessment": payload["gate4"]["candidate_surface_assessment"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
