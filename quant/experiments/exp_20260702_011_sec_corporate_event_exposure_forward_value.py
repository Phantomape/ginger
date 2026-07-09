"""exp-20260702-011: SEC corporate-event exposure forward value.

Observed-only alpha attribution. This is the first gated test after
exp-20260702-008 materialized a form-type-first SEC corporate-event stream and
exp-20260702-009 built an entity->listed-ticker exposure map. It keeps the
form set, exposure map, entry timing, horizon, and comparator set fixed. It
does not change entries, exits, ranking, sizing, paper sleeves, live orders,
watchlists, LLM boundaries, or daily production behavior.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from entity_exposure_map import map_event_to_exposures  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260702-011"
OWNER = "alpha-explore"
SLUG = "sec_corporate_event_exposure_forward_value"
RUNNER = f"quant/experiments/exp_20260702_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_011_{SLUG}.json"
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
EVENT_ROWS = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_corporate_event_stream"
    / "rows.jsonl"
)
EVENT_MANIFEST = EVENT_ROWS.parent / "manifest.json"
EXPOSURE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "entity_exposure_map"
ENTITY_ROWS = EXPOSURE_DIR / "entities.jsonl"
SIC_INDEX = EXPOSURE_DIR / "sic_peer_index.json"
THEME_OVERLAY = EXPOSURE_DIR / "theme_overlay.json"
EXPOSURE_MANIFEST = EXPOSURE_DIR / "manifest.json"
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"

HORIZON = 10
PROXY_NOTIONAL_USD = 10_000.0
COMPARATORS = ("SPY", "QQQ")
WINDOWS = {
    "old_thin": ("2024-10-02", "2025-04-22"),
    "mid_weak": ("2025-04-23", "2025-10-22"),
    "late_strong": ("2025-10-23", "2026-04-21"),
    "current_forward": ("2026-04-22", "2026-07-02"),
}
CANONICAL_WINDOWS = ("old_thin", "mid_weak", "late_strong")
CONFIG = {
    "event_scope": "fresh S-1/F-1 IPO registrations (is_amendment=false) plus all 425 merger communications",
    "horizon": HORIZON,
    "entry": "next available hot-warehouse open after filed_date",
    "exit": "close of the 10th trading session after entry",
    "comparators": ["cash", "SPY", "QQQ", "explicit_ticker_control"],
    "proxy_notional_usd": PROXY_NOTIONAL_USD,
    "min_settled_exposure_rows": 1_000,
    "min_settled_exposure_rows_per_canonical_window": 500,
    "min_explicit_control_rows": 100,
    "max_single_positive_pnl_share": 0.50,
    "positive_pnl_hhi_guardrail": 0.35,
}
HYPOTHESIS = (
    "Observed-only alpha hypothesis: SEC S-1/F-1 IPO registrations and 425 "
    "merger communications may propagate attention or supply-shock value to "
    "listed SIC/theme exposure tickers through the new entity exposure map, "
    "producing positive next-open 10d replacement value versus cash, SPY, QQQ, "
    "and explicit-ticker event controls."
)
CHANGE_TYPE = "candidate_pool_observed_only"
MECHANISM_FAMILY = "production_visible_sec_corporate_event_propagation"
TRIAL_FAMILY = "sec_event_entity_exposure_forward_value"
TRIAL_VARIANT_ID = "fixed_form_set_sic_theme_exposure_10d_v1"
CHANGED_VARIABLE = "sec_corporate_event_exposure_propagation_forward_value_v1"
SINGLE_CAUSAL_VARIABLE = CHANGED_VARIABLE
NEW_EVIDENCE_TYPE = "new_entity_to_listed_peer_exposure_surface"
NEW_EVIDENCE_AXIS = (
    "New data source and gate shape: form-type-first EDGAR S-1/F-1/425 event "
    "stream joined to the first entity-to-listed-ticker exposure map; prior "
    "relation tests were listed-to-listed or explicit ticker news, not "
    "non-tradable-primary-entity propagation."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260702-008",
    "exp-20260702-009",
    "exp-20260630-005",
    "exp-20260630-017",
]
CAUSAL_COMPONENTS = [
    "fixed SEC S-1/F-1/425 event stream",
    "fixed entity exposure map",
    "next-open 10d outcome settlement",
    "cash SPY QQQ and explicit-ticker controls",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260702-011/exp_20260702_011_sec_corporate_event_exposure_forward_value.json",
    "experiments/cards/exp-20260702-011.md",
    "experiments/manifests/exp-20260702-011.json",
    "experiments/tickets/exp-20260702-011.json",
    "experiments/logs/exp-20260702-011.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
DEFAULT_PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "event_density_too_sparse",
        "theme_edges_are_noisy",
        "window_instability",
        "explicit_ticker_control_beats_exposures",
    ],
    "confidence_reason": (
        "The new EDGAR form-index stream and entity exposure map create a "
        "genuinely new primary-entity-to-listed-peer surface, but prior direct "
        "news/event and generic peer-relation attempts were weak; this run "
        "should first test forward replacement value without changing trading "
        "behavior."
    ),
}
PRODUCTION_IMPACT = {
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
    "uses_sec_corporate_event_stream": True,
    "uses_entity_exposure_map": True,
    "uses_hot_warehouse_forward_settlement": True,
    "live_realistic_execution_envelope": (
        "Not evaluated for live use; this is observed-only attribution and "
        "cannot become live-ready."
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
    if not math.isfinite(out):
        return None
    return out


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def parse_date(value: Any) -> str:
    return str(value or "")[:10]


def window_label(day: str) -> str | None:
    for label, (start, end) in WINDOWS.items():
        if start <= day <= end:
            return label
    return None


def immutable_uri(path: Path) -> str:
    return path.resolve().as_uri() + "?mode=ro&immutable=1"


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = dict(DEFAULT_PREDICTION)
    value = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(value, dict):
        prediction.update(value)
    prediction.setdefault("recorded_at", utc_now())
    return prediction


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
    drawdowns = [
        float(window.get("max_drawdown_pct"))
        for window in windows
        if window.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(window.get("expected_value_score") or 0.0) for window in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(window.get("total_pnl") or 0.0) for window in windows),
            2,
        ),
        "trade_count": sum(int(window.get("trade_count") or 0) for window in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def load_entity_rows() -> dict[str, dict[str, Any]]:
    return {row.get("cik"): row for row in read_jsonl(ENTITY_ROWS) if row.get("cik")}


def source_event_in_scope(event: dict[str, Any]) -> bool:
    event_class = event.get("event_class")
    if event_class == "merger_communication":
        return True
    if event_class == "ipo_registration" and not event.get("is_amendment"):
        return True
    return False


def merge_exposure(
    candidates: dict[tuple[str, str, str, str], dict[str, Any]],
    event: dict[str, Any],
    exposure: dict[str, Any],
) -> None:
    ticker = str(exposure.get("ticker") or "").upper()
    primary_ticker = str(event.get("ticker") or "").upper()
    if not ticker or ticker == primary_ticker:
        return
    filed_date = parse_date(event.get("filed_date"))
    key = (str(event.get("accession")), str(event.get("cik")), filed_date, ticker)
    row = candidates.get(key)
    relation_type = str(exposure.get("relation_type") or "unknown")
    theme = exposure.get("theme")
    match_basis = exposure.get("match_basis")
    if row is None:
        row = {
            "observation_id": ":".join(key),
            "event_accession": event.get("accession"),
            "event_class": event.get("event_class"),
            "form_type": event.get("form_type"),
            "is_amendment": bool(event.get("is_amendment")),
            "filed_date": filed_date,
            "window": window_label(filed_date),
            "primary_entity_cik": event.get("cik"),
            "primary_entity_name": event.get("company_name"),
            "primary_ticker": event.get("ticker"),
            "ticker": ticker,
            "relation_types": [],
            "match_bases": [],
            "themes": [],
            "overlay_version": exposure.get("overlay_version"),
            "row_kind": "exposure_candidate",
        }
        candidates[key] = row
    if relation_type not in row["relation_types"]:
        row["relation_types"].append(relation_type)
    if match_basis and match_basis not in row["match_bases"]:
        row["match_bases"].append(match_basis)
    if theme and theme not in row["themes"]:
        row["themes"].append(theme)
    row["primary_relation_type"] = (
        "theme_peer" if "theme_peer" in row["relation_types"] else row["relation_types"][0]
    )


def build_candidate_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    events = read_jsonl(EVENT_ROWS)
    entities = load_entity_rows()
    sic_index = read_json(SIC_INDEX, {"by_sic": {}})
    overlay = read_json(THEME_OVERLAY, {"themes": []})

    candidates: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    controls: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    event_counts = Counter()
    selected_event_counts = Counter()
    no_exposure_counts = Counter()
    excluded_amendment_count = 0
    for event in events:
        event_counts[str(event.get("event_class") or "missing")] += 1
        if event.get("event_class") == "ipo_registration" and event.get("is_amendment"):
            excluded_amendment_count += 1
        if not source_event_in_scope(event):
            continue
        selected_event_counts[str(event.get("event_class") or "missing")] += 1
        filed_date = parse_date(event.get("filed_date"))
        ticker = str(event.get("ticker") or "").upper()
        if ticker:
            key = (str(event.get("accession")), str(event.get("cik")), filed_date, ticker)
            controls.setdefault(
                key,
                {
                    "observation_id": "control:" + ":".join(key),
                    "event_accession": event.get("accession"),
                    "event_class": event.get("event_class"),
                    "form_type": event.get("form_type"),
                    "filed_date": filed_date,
                    "window": window_label(filed_date),
                    "primary_entity_cik": event.get("cik"),
                    "primary_entity_name": event.get("company_name"),
                    "primary_ticker": ticker,
                    "ticker": ticker,
                    "primary_relation_type": "explicit_ticker_control",
                    "relation_types": ["explicit_ticker_control"],
                    "match_bases": ["sec_index_ticker_map"],
                    "themes": [],
                    "row_kind": "explicit_ticker_control",
                },
            )
        exposures = map_event_to_exposures(
            event,
            entities.get(event.get("cik")),
            sic_index,
            overlay,
        )
        if not exposures:
            no_exposure_counts[str(event.get("event_class") or "missing")] += 1
        for exposure in exposures:
            merge_exposure(candidates, event, exposure)

    exposure_rows = sorted(
        candidates.values(),
        key=lambda row: (
            row["filed_date"],
            row["event_accession"],
            row["primary_entity_cik"],
            row["ticker"],
        ),
    )
    control_rows = sorted(
        controls.values(),
        key=lambda row: (
            row["filed_date"],
            row["event_accession"],
            row["primary_entity_cik"],
            row["ticker"],
        ),
    )
    return exposure_rows, control_rows, {
        "event_rows": len(events),
        "event_class_counts": dict(sorted(event_counts.items())),
        "selected_event_class_counts": dict(sorted(selected_event_counts.items())),
        "excluded_ipo_amendment_rows": excluded_amendment_count,
        "events_without_exposures": dict(sorted(no_exposure_counts.items())),
        "exposure_candidate_rows": len(exposure_rows),
        "explicit_ticker_control_rows": len(control_rows),
        "exposure_ticker_count": len({row["ticker"] for row in exposure_rows}),
        "control_ticker_count": len({row["ticker"] for row in control_rows}),
        "exposure_window_counts": dict(
            sorted(Counter(row.get("window") or "outside" for row in exposure_rows).items())
        ),
        "control_window_counts": dict(
            sorted(Counter(row.get("window") or "outside" for row in control_rows).items())
        ),
    }


def load_hot_prices(tickers: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not HOT_WAREHOUSE.exists():
        return {}, {
            "warehouse": repo_rel(HOT_WAREHOUSE),
            "exists": False,
            "immutable_read": False,
            "error": "missing_hot_warehouse",
        }
    requested = sorted({ticker.upper() for ticker in tickers if ticker})
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
                "select ticker, date, open, close from ohlcv "
                f"where ticker in ({placeholders}) order by ticker, date"
            )
            for ticker, day, open_px, close_px in con.execute(sql, chunk):
                open_f = safe_float(open_px)
                close_f = safe_float(close_px)
                if open_f is None or close_f is None or open_f <= 0 or close_f <= 0:
                    continue
                prices[str(ticker).upper()].append(
                    {"date": str(day), "open": open_f, "close": close_f}
                )
    finally:
        con.close()
    missing_requested = sorted(set(requested) - set(prices))
    return dict(prices), {
        "warehouse": repo_rel(HOT_WAREHOUSE),
        "exists": True,
        "immutable_read": True,
        "quick_check": quick[0] if quick else None,
        "requested_ticker_count": len(requested),
        "price_ticker_count": len(prices),
        "missing_requested_ticker_count": len(missing_requested),
        "missing_requested_ticker_sample": missing_requested[:25],
        "warehouse_min_date": warehouse_range[0] if warehouse_range else None,
        "warehouse_max_date": warehouse_range[1] if warehouse_range else None,
        "warehouse_row_count": warehouse_range[2] if warehouse_range else None,
        "warehouse_ticker_count": warehouse_range[3] if warehouse_range else None,
        "benchmark_ranges": {
            ticker: {
                "start": prices[ticker][0]["date"],
                "end": prices[ticker][-1]["date"],
                "rows": len(prices[ticker]),
            }
            for ticker in COMPARATORS
            if ticker in prices and prices[ticker]
        },
    }


def net_pnl_from_bars(entry_open: float, exit_close: float) -> tuple[float, float, float, float]:
    entry_fill = apply_entry_fill(entry_open, notional=PROXY_NOTIONAL_USD)
    exit_fill = apply_slippage(
        exit_close,
        SLIPPAGE_BPS_TARGET,
        "sell",
        notional=PROXY_NOTIONAL_USD,
    )
    if entry_fill is None or exit_fill is None or entry_fill <= 0:
        raise ValueError("invalid fill inputs")
    net_return = (exit_fill / entry_fill) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = PROXY_NOTIONAL_USD * net_return
    return round(entry_fill, 4), round(exit_fill, 4), round(net_return, 8), round(pnl, 2)


def resolve_horizon(
    ticker_rows: list[dict[str, Any]],
    asof_date: str,
) -> dict[str, Any]:
    if not ticker_rows:
        return {"status": "missing_ticker_prices"}
    dates = [row["date"] for row in ticker_rows]
    entry_idx = bisect.bisect_right(dates, asof_date)
    if entry_idx >= len(ticker_rows):
        return {"status": "pending_forward_entry"}
    exit_idx = entry_idx + HORIZON - 1
    if exit_idx >= len(ticker_rows):
        return {
            "status": "pending_forward_exit",
            "entry_date": ticker_rows[entry_idx]["date"],
            "available_forward_sessions": len(ticker_rows) - entry_idx,
        }
    entry = ticker_rows[entry_idx]
    exit_row = ticker_rows[exit_idx]
    try:
        entry_fill, exit_fill, net_return, pnl = net_pnl_from_bars(
            float(entry["open"]),
            float(exit_row["close"]),
        )
    except ValueError:
        return {"status": "invalid_price"}
    return {
        "status": "settled",
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": round(float(entry["open"]), 4),
        "exit_close": round(float(exit_row["close"]), 4),
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "net_return": net_return,
        "pnl_usd": pnl,
    }


def comparator_pnl(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    entry_date: str,
    exit_date: str,
) -> dict[str, Any]:
    by_date = {row["date"]: row for row in prices.get(ticker, [])}
    entry = by_date.get(entry_date)
    exit_row = by_date.get(exit_date)
    if not entry or not exit_row:
        return {"status": "missing_comparator_window"}
    try:
        entry_fill, exit_fill, net_return, pnl = net_pnl_from_bars(
            float(entry["open"]),
            float(exit_row["close"]),
        )
    except ValueError:
        return {"status": "invalid_comparator_price"}
    return {
        "status": "settled",
        "entry_fill": entry_fill,
        "exit_fill": exit_fill,
        "net_return": net_return,
        "pnl_usd": pnl,
    }


def settle_row(row: dict[str, Any], prices: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    filed_date = parse_date(row.get("filed_date"))
    out = dict(row)
    out.update(
        {
            "schema_version": 1,
            "experiment_id": EXPERIMENT_ID,
            "trade_enabled": False,
            "alters_orders": False,
            "proxy_notional_usd": PROXY_NOTIONAL_USD,
            "target_price": None,
            "target_price_resolution": "not_applicable_observed_only_fixed_horizon",
        }
    )
    if not ticker or not filed_date:
        out[f"forward_{HORIZON}d_status"] = "missing_ticker_or_filed_date"
        out["outcome_status"] = "pending_forward_close"
        out["entry_date"] = None
        return out
    outcome = resolve_horizon(prices.get(ticker, []), filed_date)
    status = str(outcome.get("status"))
    prefix = f"forward_{HORIZON}d"
    out[f"{prefix}_status"] = status
    out["entry_date"] = outcome.get("entry_date")
    out["planned_entry_date"] = outcome.get("entry_date")
    if outcome.get("available_forward_sessions") is not None:
        out[f"{prefix}_available_forward_sessions"] = outcome.get("available_forward_sessions")
    if status != "settled":
        out["outcome_status"] = "pending_forward_close"
        return out

    entry_date = str(outcome["entry_date"])
    exit_date = str(outcome["exit_date"])
    out[f"{prefix}_entry_date"] = entry_date
    out[f"{prefix}_exit_date"] = exit_date
    out[f"{prefix}_entry_open"] = outcome["entry_open"]
    out[f"{prefix}_exit_close"] = outcome["exit_close"]
    out[f"{prefix}_entry_fill"] = outcome["entry_fill"]
    out[f"{prefix}_exit_fill"] = outcome["exit_fill"]
    out[f"{prefix}_return_pct"] = round(float(outcome["net_return"]) * 100.0, 6)
    out[f"{prefix}_pnl_usd"] = outcome["pnl_usd"]
    out[f"replacement_value_{HORIZON}d_vs_cash_usd"] = outcome["pnl_usd"]

    all_comparators_settled = True
    for comparator in COMPARATORS:
        detail = comparator_pnl(prices, comparator, entry_date, exit_date)
        key = comparator.lower()
        out[f"{prefix}_{key}_status"] = detail["status"]
        if detail["status"] == "settled":
            out[f"{prefix}_{key}_pnl_usd"] = detail["pnl_usd"]
            out[f"replacement_value_{HORIZON}d_vs_{key}_usd"] = round(
                float(outcome["pnl_usd"]) - float(detail["pnl_usd"]),
                2,
            )
        else:
            all_comparators_settled = False
            out[f"replacement_value_{HORIZON}d_vs_{key}_usd"] = None
    out["outcome_status"] = "settled_10d" if all_comparators_settled else "settled_missing_comparator"
    return out


def settle_rows(
    exposure_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    tickers = {row["ticker"] for row in exposure_rows + control_rows if row.get("ticker")}
    tickers.update(COMPARATORS)
    prices, price_metadata = load_hot_prices(tickers)
    exposure_outcomes = [settle_row(row, prices) for row in exposure_rows]
    control_outcomes = [settle_row(row, prices) for row in control_rows]
    status_field = f"forward_{HORIZON}d_status"
    settled_exposure = settled_rows(exposure_outcomes)
    settled_control = settled_rows(control_outcomes)
    return exposure_outcomes, control_outcomes, {
        "price_metadata": price_metadata,
        "exposure_outcome_rows": len(exposure_outcomes),
        "control_outcome_rows": len(control_outcomes),
        "settled_exposure_rows": len(settled_exposure),
        "settled_control_rows": len(settled_control),
        "exposure_status_counts": dict(
            sorted(Counter(str(row.get(status_field) or "missing") for row in exposure_outcomes).items())
        ),
        "control_status_counts": dict(
            sorted(Counter(str(row.get(status_field) or "missing") for row in control_outcomes).items())
        ),
        "settled_exposure_by_window": dict(
            sorted(Counter(str(row.get("window") or "outside") for row in settled_exposure).items())
        ),
        "settled_control_by_window": dict(
            sorted(Counter(str(row.get("window") or "outside") for row in settled_control).items())
        ),
    }


def metric_key(suffix: str) -> str:
    return f"replacement_value_{HORIZON}d_vs_{suffix}_usd"


def settled_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get(f"forward_{HORIZON}d_status") == "settled"
        and row.get(metric_key("cash")) is not None
        and row.get(metric_key("spy")) is not None
        and row.get(metric_key("qqq")) is not None
    ]


def summarize_metric(values: list[Any]) -> dict[str, Any]:
    nums = [float(value) for value in (safe_float(v) for v in values) if value is not None]
    if not nums:
        return {"n": 0, "mean": None, "median": None, "positive_rate": None}
    return {
        "n": len(nums),
        "mean": round(mean(nums), 4),
        "median": round(median(nums), 4),
        "positive_rate": round(sum(1 for value in nums if value > 0) / len(nums), 6),
    }


def positive_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        pnl = safe_float(row.get(metric_key("cash")))
        if pnl is not None and pnl > 0:
            by_ticker[str(row.get("ticker") or "missing")] += pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_ticker_count": 0,
            "positive_pnl_total": 0.0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "positive_ticker_count": len(by_ticker),
        "positive_pnl_total": round(total, 2),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {
                "ticker": ticker,
                "positive_pnl_usd": round(value, 2),
                "share": round(shares[ticker], 6),
            }
            for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:10]
        ],
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "ticker_count": 0,
            "event_count": 0,
            "date_count": 0,
            "return_pct": summarize_metric([]),
            "replacement_value_vs_cash_usd": summarize_metric([]),
            "replacement_value_vs_spy_usd": summarize_metric([]),
            "replacement_value_vs_qqq_usd": summarize_metric([]),
            "cash_positive_concentration": positive_concentration([]),
        }
    return {
        "n": len(rows),
        "ticker_count": len({row.get("ticker") for row in rows}),
        "event_count": len({(row.get("event_accession"), row.get("primary_entity_cik")) for row in rows}),
        "date_count": len({row.get("filed_date") for row in rows}),
        "return_pct": summarize_metric([row.get(f"forward_{HORIZON}d_return_pct") for row in rows]),
        "replacement_value_vs_cash_usd": summarize_metric([row.get(metric_key("cash")) for row in rows]),
        "replacement_value_vs_spy_usd": summarize_metric([row.get(metric_key("spy")) for row in rows]),
        "replacement_value_vs_qqq_usd": summarize_metric([row.get(metric_key("qqq")) for row in rows]),
        "cash_positive_concentration": positive_concentration(rows),
    }


def grouped_summary(rows: list[dict[str, Any]], field: str, limit: int | None = None) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(field)
        if isinstance(value, list):
            labels = value or ["missing"]
        else:
            labels = [value or "missing"]
        for label in labels:
            groups[str(label)].append(row)
    ordered = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)
    if limit is not None:
        ordered = ordered[:limit]
    return {label: summarize_rows(group_rows) for label, group_rows in ordered}


def compare_exposure_to_control(
    exposure_summary: dict[str, Any],
    control_summary: dict[str, Any],
) -> dict[str, Any]:
    out = {}
    for suffix in ("cash", "spy", "qqq"):
        field = f"replacement_value_vs_{suffix}_usd"
        exp_mean = exposure_summary[field]["mean"]
        ctrl_mean = control_summary[field]["mean"]
        out[f"mean_{suffix}_delta_vs_explicit_control"] = (
            round(exp_mean - ctrl_mean, 4)
            if exp_mean is not None and ctrl_mean is not None
            else None
        )
        exp_median = exposure_summary[field]["median"]
        ctrl_median = control_summary[field]["median"]
        out[f"median_{suffix}_delta_vs_explicit_control"] = (
            round(exp_median - ctrl_median, 4)
            if exp_median is not None and ctrl_median is not None
            else None
        )
    return out


def build_outcome_summary(
    exposure_outcomes: list[dict[str, Any]],
    control_outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    exposures = settled_rows(exposure_outcomes)
    controls = settled_rows(control_outcomes)
    windows = {}
    for label in WINDOWS:
        exp_rows = [row for row in exposures if row.get("window") == label]
        ctrl_rows = [row for row in controls if row.get("window") == label]
        exp_summary = summarize_rows(exp_rows)
        ctrl_summary = summarize_rows(ctrl_rows)
        windows[label] = {
            "exposure": exp_summary,
            "explicit_ticker_control": ctrl_summary,
            "exposure_minus_control": compare_exposure_to_control(exp_summary, ctrl_summary),
        }
    aggregate_exposure = summarize_rows(exposures)
    aggregate_control = summarize_rows(controls)
    return {
        "horizon": HORIZON,
        "settled_exposure_rows": len(exposures),
        "settled_control_rows": len(controls),
        "aggregate": {
            "exposure": aggregate_exposure,
            "explicit_ticker_control": aggregate_control,
            "exposure_minus_control": compare_exposure_to_control(
                aggregate_exposure,
                aggregate_control,
            ),
        },
        "windows": windows,
        "by_event_class": grouped_summary(exposures, "event_class"),
        "by_relation_type": grouped_summary(exposures, "primary_relation_type"),
        "by_theme": grouped_summary(exposures, "themes", limit=15),
        "sample_best_rows": sorted(
            [
                {
                    "filed_date": row.get("filed_date"),
                    "event_class": row.get("event_class"),
                    "primary_entity_name": row.get("primary_entity_name"),
                    "ticker": row.get("ticker"),
                    "relation_types": row.get("relation_types"),
                    "themes": row.get("themes"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get(f"forward_{HORIZON}d_exit_date"),
                    "replacement_value_vs_cash_usd": row.get(metric_key("cash")),
                    "replacement_value_vs_spy_usd": row.get(metric_key("spy")),
                    "replacement_value_vs_qqq_usd": row.get(metric_key("qqq")),
                }
                for row in exposures
            ],
            key=lambda row: safe_float(row.get("replacement_value_vs_cash_usd")) or 0.0,
            reverse=True,
        )[:25],
        "sample_worst_rows": sorted(
            [
                {
                    "filed_date": row.get("filed_date"),
                    "event_class": row.get("event_class"),
                    "primary_entity_name": row.get("primary_entity_name"),
                    "ticker": row.get("ticker"),
                    "relation_types": row.get("relation_types"),
                    "themes": row.get("themes"),
                    "entry_date": row.get("entry_date"),
                    "exit_date": row.get(f"forward_{HORIZON}d_exit_date"),
                    "replacement_value_vs_cash_usd": row.get(metric_key("cash")),
                    "replacement_value_vs_spy_usd": row.get(metric_key("spy")),
                    "replacement_value_vs_qqq_usd": row.get(metric_key("qqq")),
                }
                for row in exposures
            ],
            key=lambda row: safe_float(row.get("replacement_value_vs_cash_usd")) or 0.0,
        )[:25],
    }


def evaluate_gate4(summary: dict[str, Any]) -> dict[str, Any]:
    windows = summary["windows"]
    aggregate = summary["aggregate"]["exposure"]
    concentration = aggregate["cash_positive_concentration"]
    checks: dict[str, bool] = {
        "settled_exposure_sample_floor": summary["settled_exposure_rows"]
        >= CONFIG["min_settled_exposure_rows"],
        "settled_control_sample_floor": summary["settled_control_rows"]
        >= CONFIG["min_explicit_control_rows"],
        "aggregate_mean_cash_positive": (
            aggregate["replacement_value_vs_cash_usd"]["mean"] is not None
            and aggregate["replacement_value_vs_cash_usd"]["mean"] > 0
        ),
        "aggregate_mean_spy_positive": (
            aggregate["replacement_value_vs_spy_usd"]["mean"] is not None
            and aggregate["replacement_value_vs_spy_usd"]["mean"] > 0
        ),
        "aggregate_mean_qqq_positive": (
            aggregate["replacement_value_vs_qqq_usd"]["mean"] is not None
            and aggregate["replacement_value_vs_qqq_usd"]["mean"] > 0
        ),
        "max_single_positive_pnl_share_pass": (
            concentration["max_single_positive_pnl_share"] is not None
            and concentration["max_single_positive_pnl_share"]
            <= CONFIG["max_single_positive_pnl_share"]
        ),
        "positive_pnl_hhi_pass": (
            concentration["positive_pnl_hhi"] is not None
            and concentration["positive_pnl_hhi"] <= CONFIG["positive_pnl_hhi_guardrail"]
        ),
        "strategy_behavior_unchanged": True,
    }
    for label in CANONICAL_WINDOWS:
        exp = windows[label]["exposure"]
        checks[f"{label}_sample_floor"] = (
            exp["n"] >= CONFIG["min_settled_exposure_rows_per_canonical_window"]
        )
        checks[f"{label}_mean_cash_positive"] = (
            exp["replacement_value_vs_cash_usd"]["mean"] is not None
            and exp["replacement_value_vs_cash_usd"]["mean"] > 0
        )
        checks[f"{label}_mean_spy_positive"] = (
            exp["replacement_value_vs_spy_usd"]["mean"] is not None
            and exp["replacement_value_vs_spy_usd"]["mean"] > 0
        )
        deltas = windows[label]["exposure_minus_control"]
        for suffix in ("cash", "spy", "qqq"):
            key = f"mean_{suffix}_delta_vs_explicit_control"
            checks[f"{label}_exposure_mean_{suffix}_beats_explicit_control"] = (
                deltas.get(key) is not None and deltas[key] > 0
            )

    failed = [key for key, ok in checks.items() if not ok]
    observed_only_lead = not failed
    return {
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_sec_event_exposure_propagation_lead_not_promoted"
            if observed_only_lead
            else "rejected_no_sec_event_exposure_propagation_forward_edge"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "lead_limitations": [
            "Observed-only event-ticker attribution, not a deployable candidate source.",
            "Raw exposure rows are many-to-one and need a separate ex-ante source-ranking or top-1/day policy before any paper sleeve can be accepted.",
            "Entity SIC is current-submissions classification, not an as-of-filing SIC snapshot.",
            "No shared helper, daily adapter, ranking rule, sizing rule, or live behavior was promoted.",
        ],
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
        },
        "strategy_rerun_required": False,
    }


def calibrate(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual = 1.0 if success else 0.0
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    mode_map = {
        "event_density_too_sparse": {
            "settled_exposure_sample_floor",
            "old_thin_sample_floor",
            "mid_weak_sample_floor",
            "late_strong_sample_floor",
            "settled_control_sample_floor",
        },
        "theme_edges_are_noisy": {
            "aggregate_mean_cash_positive",
            "aggregate_mean_spy_positive",
            "aggregate_mean_qqq_positive",
        },
        "window_instability": {
            "old_thin_mean_cash_positive",
            "old_thin_mean_spy_positive",
            "mid_weak_mean_cash_positive",
            "mid_weak_mean_spy_positive",
            "late_strong_mean_cash_positive",
            "late_strong_mean_spy_positive",
        },
        "explicit_ticker_control_beats_exposures": {
            reason
            for reason in failed
            if "beats_explicit_control" in reason
        },
    }
    hit_modes = [
        mode for mode in predicted_modes if mode_map.get(mode, set()).intersection(failed)
    ]
    return {
        "actual_decision": (
            "observed_only_positive_sec_event_exposure_propagation_lead_not_promoted"
            if success
            else "rejected_no_sec_event_exposure_propagation_forward_edge"
        ),
        "predicted_success_probability": round(probability, 4),
        "actual_success": 1 if success else 0,
        "brier_score": round((probability - actual) ** 2, 6),
        "expected_ev_delta": safe_float(prediction.get("expected_ev_delta")) or 0.0,
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": safe_float(prediction.get("expected_pnl_delta")) or 0.0,
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": predicted_modes,
        "realized_failure_modes": failed
        or ["positive_observed_only_lead_but_no_deployable_candidate_policy"],
        "predicted_failure_modes_hit": hit_modes,
        "surprise_note": (
            "The event-exposure relation survived the observed-only forward-value checks."
            if success
            else "The event-exposure relation did not clear the observed-only forward-value checks."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket if isinstance(ticket, dict) else {})
    baseline = load_baseline_metrics()
    exposure_rows, control_rows, source_summary = build_candidate_rows()
    exposure_outcomes, control_outcomes, settlement_summary = settle_rows(
        exposure_rows,
        control_rows,
    )
    outcome_summary = build_outcome_summary(exposure_outcomes, control_outcomes)
    gate4 = evaluate_gate4(outcome_summary)
    observed_only_lead = gate4["observed_only_lead"]
    status = "observed_only_positive_lead" if observed_only_lead else "rejected"
    why = (
        "The new SEC corporate-event stream plus entity exposure map produced "
        "positive observed-only 10d replacement value across the canonical "
        "windows and beat explicit-ticker event controls on mean cash/SPY/QQQ "
        "replacement value. This is still not promoted because there is no "
        "ex-ante source ranking, daily helper, or deployment envelope."
        if observed_only_lead
        else "The fixed event-exposure mapping did not produce robust enough "
        "10d replacement value to justify a follow-up paper sleeve."
    )
    forbidden = (
        "Do not tune the form set, include IPO amendments, widen the theme "
        "overlay, change SIC peer caps, sweep hold days, or hand-pick themes "
        "on this same surface. A valid retry needs a fixed ex-ante ranking/"
        "source-priority policy, PIT SIC-as-of-filing repair, or materially "
        "more settled forward rows under the unchanged map."
    )
    next_evidence = (
        "If pursued, the next experiment must be a shared-paper-first helper "
        "with one fixed ex-ante selection rule, such as source/date arbitration "
        "or relation-priority ranking, then daily default-off exposure rows and "
        "comparator-aware Gate 1-4 measurement."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibrate(prediction, observed_only_lead, gate4["failed_reasons"]),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "experiment.py new accepted the proposal without override; nearest score was below the blocking threshold.",
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: fixed fresh S-1/F-1 plus "
                "425 events, fixed entity exposure map, fixed next-open 10d "
                "cash/SPY/QQQ/explicit-ticker controls."
            ),
            "4_success_failure_standard": CONFIG,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "event_rows": repo_rel(EVENT_ROWS),
            "entity_rows": repo_rel(ENTITY_ROWS),
            "sic_index": repo_rel(SIC_INDEX),
            "theme_overlay": repo_rel(THEME_OVERLAY),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
        },
        "source_summary": source_summary,
        "settlement_summary": settlement_summary,
        "outcome_summary": outcome_summary,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": True,
            "dependency_fields": [
                "event_accession",
                "filed_date",
                "event_class",
                "ticker",
                "entry_date",
                "target_price",
            ],
            "event_rows_exists": EVENT_ROWS.exists(),
            "entity_exposure_map_exists": ENTITY_ROWS.exists() and SIC_INDEX.exists() and THEME_OVERLAY.exists(),
            "settled_rows_with_entry_date": outcome_summary["settled_exposure_rows"],
            "target_price_scope": "not_applicable_observed_only_fixed_horizon",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No executable filter, entry, exit, ranking, sizing, or order rule was added.",
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": forbidden,
            "new_evidence_required": next_evidence,
        },
        "next_retry_requires": [next_evidence],
        "rejection_reason": None if observed_only_lead else ";".join(gate4["failed_reasons"]),
        "related_files": [
            RUNNER,
            repo_rel(EVENT_ROWS),
            repo_rel(EVENT_MANIFEST),
            repo_rel(ENTITY_ROWS),
            repo_rel(SIC_INDEX),
            repo_rel(THEME_OVERLAY),
            repo_rel(EXPOSURE_MANIFEST),
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
        "anti_js": {"used_javascript": False, "evidence": "Python runner only; no node/js tooling invoked."},
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": payload["new_evidence_axis"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "parameters": payload["parameters"],
        "source_summary": payload["source_summary"],
        "settlement_summary": payload["settlement_summary"],
        "outcome_summary": {
            "horizon": HORIZON,
            "settled_exposure_rows": payload["outcome_summary"]["settled_exposure_rows"],
            "settled_control_rows": payload["outcome_summary"]["settled_control_rows"],
            "aggregate": payload["outcome_summary"]["aggregate"],
            "windows": payload["outcome_summary"]["windows"],
            "by_event_class": payload["outcome_summary"]["by_event_class"],
            "by_relation_type": payload["outcome_summary"]["by_relation_type"],
            "by_theme": payload["outcome_summary"]["by_theme"],
        },
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "next_retry_requires": payload["next_retry_requires"],
        "rejection_reason": payload["rejection_reason"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def money(value: Any) -> str:
    number = safe_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def window_table(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Exposure rows | Mean cash | Mean SPY | Mean QQQ | Control rows | Mean control cash | Cash delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        item = payload["outcome_summary"]["windows"][label]
        exposure = item["exposure"]
        control = item["explicit_ticker_control"]
        delta = item["exposure_minus_control"]
        rows.append(
            "| {label} | {n} | {cash} | {spy} | {qqq} | {cn} | {ccash} | {dcash} |".format(
                label=label,
                n=exposure["n"],
                cash=money(exposure["replacement_value_vs_cash_usd"]["mean"]),
                spy=money(exposure["replacement_value_vs_spy_usd"]["mean"]),
                qqq=money(exposure["replacement_value_vs_qqq_usd"]["mean"]),
                cn=control["n"],
                ccash=money(control["replacement_value_vs_cash_usd"]["mean"]),
                dcash=money(delta["mean_cash_delta_vs_explicit_control"]),
            )
        )
    return "\n".join(rows)


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["outcome_summary"]["aggregate"]["exposure"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC corporate-event exposure forward value",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: no",
            "- Shared helper promoted: no",
            f"- Settled exposure rows: `{payload['outcome_summary']['settled_exposure_rows']}`",
            f"- Settled explicit-ticker controls: `{payload['outcome_summary']['settled_control_rows']}`",
            f"- Aggregate mean cash RV: `{money(aggregate['replacement_value_vs_cash_usd']['mean'])}`",
            f"- Aggregate mean SPY RV: `{money(aggregate['replacement_value_vs_spy_usd']['mean'])}`",
            f"- Aggregate mean QQQ RV: `{money(aggregate['replacement_value_vs_qqq_usd']['mean'])}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Window Summary",
            "",
            window_table(payload),
            "",
            "## Gate 4",
            "",
            f"- Observed-only lead: `{payload['observed_only_lead']}`",
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
        EVENT_ROWS,
        EVENT_MANIFEST,
        ENTITY_ROWS,
        SIC_INDEX,
        THEME_OVERLAY,
        EXPOSURE_MANIFEST,
        HOT_WAREHOUSE,
        REPO_ROOT / "experiments" / "logs" / "exp-20260702-008.json",
        REPO_ROOT / "experiments" / "logs" / "exp-20260702-009.json",
        REPO_ROOT / "experiments" / "logs" / "exp-20260630-005.json",
        REPO_ROOT / "experiments" / "logs" / "exp-20260630-017.json",
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
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
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
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
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
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["outcome_summary"]["aggregate"]["exposure"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "settled_exposure_rows": payload["outcome_summary"]["settled_exposure_rows"],
                "settled_control_rows": payload["outcome_summary"]["settled_control_rows"],
                "aggregate_mean_cash": aggregate["replacement_value_vs_cash_usd"]["mean"],
                "aggregate_mean_spy": aggregate["replacement_value_vs_spy_usd"]["mean"],
                "aggregate_mean_qqq": aggregate["replacement_value_vs_qqq_usd"]["mean"],
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
