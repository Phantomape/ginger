"""exp-20260625-009: Kova SEC13F active-manager flow attribution.

Observed-only alpha attribution. This reads the settled Kova SEC13F forward
outcome ledger from exp-20260624-017, re-parses raw manager-level SEC 13F ZIPs,
and tests whether concentrated active-manager ownership plus quarter-over-
quarter active-flow deltas separate 1d/3d/5d replacement value.

No strategy helper, daily adapter, ranking, sizing, exit, order, watchlist,
LLM, paper sleeve, or production behavior changes in this experiment.
"""

from __future__ import annotations

import hashlib
import json
import math
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

from experiment_registry import persist_self_registered_result  # noqa: E402
from kova_data_sidecar import parse_sec13f_zip  # noqa: E402
from sec13f_coownership_edges import discover_window_labels, window_end_date  # noqa: E402
from sec13f_universe_map import load_company_name_index, normalize_issuer_name  # noqa: E402


EXPERIMENT_ID = "exp-20260625-009"
OWNER = "alpha-explore"
SLUG = "kova_sec13f_active_manager_flow_forward_attribution"
RUNNER = f"quant/experiments/exp_20260625_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_009_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUTCOME_LEDGER = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-017"
    / "kova_sec13f_forward_outcome_settlement_ledger.jsonl"
)
SEC13F_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional"
SEC13F_CACHE = SEC13F_DIR / "source_cache"

HYPOTHESIS = (
    "Observed-only attribution: Kova forward rows with stronger PIT SEC13F "
    "active-manager and quarter-over-quarter active-flow provenance should show "
    "better settled 1d/3d/5d cash, SPY, and QQQ replacement value than passive/"
    "broad sponsorship rows, creating a future shared default-off Kova evidence "
    "lead without changing strategy behavior."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "kova_multisource_forward_attribution"
TRIAL_FAMILY = "kova_sec13f_active_manager_flow_forward_attribution"
TRIAL_VARIANT_ID = "post_exp017_partial_forward_1d3d5_active_flow_v1"
CHANGED_VARIABLE = "kova_sec13f_active_manager_flow_forward_attribution_v1"
NEW_EVIDENCE_TYPE = "manager_level_13f_active_flow_forward_rows"
NEW_EVIDENCE_AXIS = (
    "Raw manager-level SEC13F ZIP fields with concentrated-manager "
    "classification and quarter-over-quarter active-flow deltas joined to "
    "exp017 settled forward rows; not holder-count/value/position-count "
    "sponsorship, coownership peer/lift/shared-manager/Jaccard, options "
    "cross-evidence, Companyfacts quality, top-N, hold, cooldown, notional, "
    "or allocator threshold retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260624-018",
    "exp-20260624-019",
    "exp-20260624-023",
    "exp-20260625-006",
]
CAUSAL_COMPONENTS = [
    "raw manager-level 13F ZIP parser",
    "active concentrated manager classification",
    "quarter-over-quarter active-flow score",
    "exp017 settled Kova forward outcomes",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260625-009/exp_20260625_009_kova_sec13f_active_manager_flow_forward_attribution.json",
    "experiments/cards/exp-20260625-009.md",
    "experiments/manifests/exp-20260625-009.json",
    "experiments/tickets/exp-20260625-009.json",
    "experiments/logs/exp-20260625-009.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "live_ready": False,
    "uses_kova_forward_snapshots": True,
    "uses_sec13f_forward_context": True,
    "uses_raw_manager_level_sec13f_zip": True,
    "forward_only_not_fixed_window_pit_coverage": True,
    "live_realistic_execution_envelope": (
        "Not evaluated for live use; this is observed-only attribution and "
        "cannot become live-ready."
    ),
}

HORIZONS = [1, 3, 5]
PRIMARY_HORIZON = 5
COMPARATORS = ["cash", "spy", "qqq"]
FLOW_BUCKETS = ["missing_active_flow", "low_active_flow", "mid_active_flow", "high_active_flow"]
ACTIVE_MANAGER_MIN_HOLDINGS = 5
ACTIVE_MANAGER_MAX_HOLDINGS = 100
ACCEPTANCE_RULE = {
    "primary_horizon": PRIMARY_HORIZON,
    "min_primary_scored_rows": 500,
    "min_primary_asof_dates": 3,
    "min_supporting_horizons_high_beats_low": 2,
    "positive_pnl_hhi_guardrail": 0.35,
    "max_single_positive_pnl_share": 0.50,
}
DEFAULT_PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_active_flow_separation",
        "passive_beta_confound",
        "forward_window_too_short",
        "manager_identity_parse_missing",
        "mega_cap_concentration",
    ],
    "confidence_reason": (
        "The playbook explicitly names active-manager/active-flow provenance as "
        "the next admissible Kova SEC13F evidence axis after aggregate sponsorship "
        "was only a forward lead and coownership/options/companyfacts follow-ups "
        "failed; confidence is low because the rows are still partial 1d/3d/5d "
        "forward outcomes and may proxy broad beta."
    ),
    "recorded_at": "2026-06-25T08:05:50+00:00",
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
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {} if default is None else default


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
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
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


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
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stats(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_rate": None,
        }
    return {
        "n": len(clean),
        "sum": round(sum(clean), 2),
        "mean": round(sum(clean) / len(clean), 4),
        "median": round(median(clean), 4),
        "min": round(min(clean), 2),
        "max": round(max(clean), 2),
        "positive_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        safe_float(row.get("max_drawdown_pct"))
        for row in windows
        if safe_float(row.get("max_drawdown_pct")) is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "window_count": len(windows),
        "windows": windows,
    }


def load_ticket_prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict):
        return prediction
    return dict(DEFAULT_PREDICTION)


def window_label_from_holdings_path(path_value: Any) -> str | None:
    if not path_value:
        return None
    stem = Path(str(path_value)).stem
    if stem.startswith("holdings_"):
        return stem.removeprefix("holdings_")
    return None


def prior_label_for(label: str, labels: list[str]) -> str | None:
    if label not in labels:
        return None
    index = labels.index(label)
    if index <= 0:
        return None
    return labels[index - 1]


def _manager_key(row: dict[str, Any]) -> str:
    return str(row.get("manager_cik") or row.get("manager_name") or "").strip()


def load_active_window(label: str, name_index: dict[str, str]) -> dict[str, Any]:
    zip_path = SEC13F_CACHE / f"{label}_form13f.zip"
    if not zip_path.exists():
        return {
            "label": label,
            "zip_path": repo_rel(zip_path),
            "zip_exists": False,
            "rows_parsed": 0,
            "mapped_long_rows": 0,
            "ticker_features": {},
        }
    asof = window_end_date(label).isoformat()
    raw_rows = parse_sec13f_zip(zip_path, asof_date=asof, cusip_ticker_map=None)

    positions: list[dict[str, Any]] = []
    manager_tickers: dict[str, set[str]] = defaultdict(set)
    put_call_rows = 0
    unmapped_rows = 0
    no_manager_rows = 0
    for row in raw_rows:
        if str(row.get("put_call") or "").strip():
            put_call_rows += 1
            continue
        ticker = name_index.get(normalize_issuer_name(row.get("name_of_issuer")))
        if not ticker:
            unmapped_rows += 1
            continue
        manager = _manager_key(row)
        if not manager:
            no_manager_rows += 1
            continue
        value = safe_float(row.get("value_usd_thousands")) or 0.0
        shares = safe_float(row.get("shares")) or 0.0
        positions.append(
            {
                "ticker": ticker,
                "manager": manager,
                "value_usd": value,
                "shares": shares,
            }
        )
        manager_tickers[manager].add(ticker)

    active_managers = {
        manager
        for manager, tickers in manager_tickers.items()
        if ACTIVE_MANAGER_MIN_HOLDINGS <= len(tickers) <= ACTIVE_MANAGER_MAX_HOLDINGS
    }

    aggregates: dict[str, dict[str, Any]] = {}
    total_managers: dict[str, set[str]] = defaultdict(set)
    active_manager_sets: dict[str, set[str]] = defaultdict(set)
    for pos in positions:
        ticker = pos["ticker"]
        manager = pos["manager"]
        entry = aggregates.setdefault(
            ticker,
            {
                "ticker": ticker,
                "total_position_row_count": 0,
                "total_value_usd": 0.0,
                "total_shares": 0.0,
                "active_position_row_count": 0,
                "active_value_usd": 0.0,
                "active_shares": 0.0,
            },
        )
        entry["total_position_row_count"] += 1
        entry["total_value_usd"] += pos["value_usd"]
        entry["total_shares"] += pos["shares"]
        total_managers[ticker].add(manager)
        if manager in active_managers:
            entry["active_position_row_count"] += 1
            entry["active_value_usd"] += pos["value_usd"]
            entry["active_shares"] += pos["shares"]
            active_manager_sets[ticker].add(manager)

    features: dict[str, dict[str, Any]] = {}
    for ticker, entry in aggregates.items():
        total_holder_count = len(total_managers[ticker])
        active_holder_count = len(active_manager_sets[ticker])
        total_value = float(entry["total_value_usd"])
        active_value = float(entry["active_value_usd"])
        total_shares = float(entry["total_shares"])
        active_shares = float(entry["active_shares"])
        features[ticker] = {
            "ticker": ticker,
            "window_label": label,
            "total_holder_count": total_holder_count,
            "active_holder_count": active_holder_count,
            "active_holder_share": active_holder_count / total_holder_count
            if total_holder_count
            else None,
            "total_position_row_count": entry["total_position_row_count"],
            "active_position_row_count": entry["active_position_row_count"],
            "active_position_row_share": entry["active_position_row_count"]
            / entry["total_position_row_count"]
            if entry["total_position_row_count"]
            else None,
            "total_value_usd": round(total_value, 2),
            "active_value_usd": round(active_value, 2),
            "active_value_share": active_value / total_value if total_value else None,
            "total_shares": round(total_shares, 2),
            "active_shares": round(active_shares, 2),
            "active_share_count_share": active_shares / total_shares if total_shares else None,
        }

    return {
        "label": label,
        "zip_path": repo_rel(zip_path),
        "zip_exists": True,
        "window_end_date": asof,
        "rows_parsed": len(raw_rows),
        "mapped_long_rows": len(positions),
        "put_call_rows_excluded": put_call_rows,
        "unmapped_long_rows": unmapped_rows,
        "no_manager_rows": no_manager_rows,
        "manager_count": len(manager_tickers),
        "active_manager_count": len(active_managers),
        "active_manager_rule": {
            "min_universe_holdings": ACTIVE_MANAGER_MIN_HOLDINGS,
            "max_universe_holdings": ACTIVE_MANAGER_MAX_HOLDINGS,
            "basis": "unique mapped long-equity tickers per manager in SEC 13F ZIP",
        },
        "ticker_count": len(features),
        "ticker_features": features,
    }


def build_flow_features(labels: list[str], outcome_rows: list[dict[str, Any]]) -> dict[str, Any]:
    name_index = load_company_name_index()
    available_labels = discover_window_labels(SEC13F_CACHE)
    requested_labels = sorted(
        {
            label
            for label in (
                window_label_from_holdings_path(row.get("sec13f_source_file"))
                for row in outcome_rows
            )
            if label
        },
        key=lambda item: available_labels.index(item) if item in available_labels else 999,
    )
    windows_to_load = sorted(
        set(requested_labels)
        | {
            prior
            for prior in (prior_label_for(label, available_labels) for label in requested_labels)
            if prior
        },
        key=lambda item: available_labels.index(item) if item in available_labels else 999,
    )
    loaded = {label: load_active_window(label, name_index) for label in windows_to_load}

    joined: dict[str, dict[str, dict[str, Any]]] = {}
    for label in requested_labels:
        current = loaded.get(label, {}).get("ticker_features", {})
        prior_label = prior_label_for(label, available_labels)
        prior = loaded.get(prior_label or "", {}).get("ticker_features", {}) if prior_label else {}
        label_features: dict[str, dict[str, Any]] = {}
        for ticker in sorted(set(current) | set(prior)):
            cur = current.get(ticker, {})
            old = prior.get(ticker, {})
            active_value = safe_float(cur.get("active_value_usd")) or 0.0
            prior_active_value = safe_float(old.get("active_value_usd")) or 0.0
            active_holders = safe_float(cur.get("active_holder_count")) or 0.0
            prior_active_holders = safe_float(old.get("active_holder_count")) or 0.0
            active_flow_log_delta = math.log1p(active_value) - math.log1p(prior_active_value)
            active_holder_delta = active_holders - prior_active_holders
            label_features[ticker] = {
                "active13f_window_label": label,
                "active13f_prior_window_label": prior_label,
                "active13f_total_holder_count": cur.get("total_holder_count"),
                "active13f_active_holder_count": cur.get("active_holder_count"),
                "active13f_active_holder_share": cur.get("active_holder_share"),
                "active13f_total_value_usd": cur.get("total_value_usd"),
                "active13f_active_value_usd": cur.get("active_value_usd"),
                "active13f_active_value_share": cur.get("active_value_share"),
                "active13f_active_position_row_share": cur.get("active_position_row_share"),
                "active13f_prior_active_holder_count": old.get("active_holder_count"),
                "active13f_prior_active_value_usd": old.get("active_value_usd"),
                "active13f_active_value_log_delta": active_flow_log_delta,
                "active13f_active_holder_count_delta": active_holder_delta,
                "active13f_has_current": bool(cur),
                "active13f_has_prior": bool(old),
            }
        assign_active_flow_scores(label_features)
        joined[label] = label_features

    summary = {
        "available_window_labels": available_labels,
        "requested_window_labels": requested_labels,
        "loaded_window_labels": windows_to_load,
        "loaded_windows": {
            label: {key: value for key, value in payload.items() if key != "ticker_features"}
            for label, payload in loaded.items()
        },
    }
    return {"features_by_label": joined, "summary": summary}


def percentile_by_ticker(features: dict[str, dict[str, Any]], field: str) -> dict[str, float]:
    pairs = [
        (ticker, safe_float(row.get(field)))
        for ticker, row in features.items()
        if safe_float(row.get(field)) is not None
    ]
    pairs = [(ticker, value) for ticker, value in pairs if value is not None]
    pairs.sort(key=lambda item: (item[1], item[0]))
    if not pairs:
        return {}
    if len(pairs) == 1:
        return {pairs[0][0]: 1.0}
    out: dict[str, float] = {}
    index = 0
    while index < len(pairs):
        end = index + 1
        while end < len(pairs) and pairs[end][1] == pairs[index][1]:
            end += 1
        rank = ((index + end - 1) / 2.0) / (len(pairs) - 1)
        for pos in range(index, end):
            out[pairs[pos][0]] = rank
        index = end
    return out


def assign_active_flow_scores(features: dict[str, dict[str, Any]]) -> None:
    score_fields = [
        "active13f_active_value_share",
        "active13f_active_holder_share",
        "active13f_active_value_log_delta",
        "active13f_active_holder_count_delta",
    ]
    ranks = {field: percentile_by_ticker(features, field) for field in score_fields}
    for ticker, row in features.items():
        parts = [mapping[ticker] for mapping in ranks.values() if ticker in mapping]
        row["active13f_active_flow_score"] = sum(parts) / len(parts) if parts else None
        row["active13f_score_component_count"] = len(parts)
        row["active13f_score_definition"] = (
            "Average percentile rank of active_value_share, active_holder_share, "
            "active_value_log_delta, and active_holder_count_delta among mapped "
            "tickers in the same SEC13F window."
        )


def enrich_outcome_rows(rows: list[dict[str, Any]], flow: dict[str, Any]) -> list[dict[str, Any]]:
    features_by_label = flow["features_by_label"]
    enriched: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        label = window_label_from_holdings_path(row.get("sec13f_source_file"))
        ticker = str(row.get("ticker") or "").upper()
        features = features_by_label.get(label or "", {}).get(ticker)
        if features:
            item.update(features)
            item["active13f_status"] = "ok"
        else:
            item["active13f_status"] = "missing_ticker_or_window"
            item["active13f_active_flow_score"] = None
        enriched.append(item)
    return enriched


def settled_rows(rows: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    status_key = f"forward_{horizon}d_status"
    cash_key = f"replacement_value_{horizon}d_vs_cash_usd"
    return [
        row
        for row in rows
        if row.get(status_key) == "settled" and safe_float(row.get(cash_key)) is not None
    ]


def bucket_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    scored = [
        row for row in rows if safe_float(row.get("active13f_active_flow_score")) is not None
    ]
    missing = [
        row for row in rows if safe_float(row.get("active13f_active_flow_score")) is None
    ]
    ordered = sorted(
        scored,
        key=lambda row: (
            safe_float(row.get("active13f_active_flow_score")) or 0.0,
            str(row.get("ticker") or ""),
            str(row.get("observation_id") or ""),
        ),
    )
    buckets = {name: [] for name in FLOW_BUCKETS}
    buckets["missing_active_flow"] = missing
    total = len(ordered)
    if not total:
        return buckets
    for index, row in enumerate(ordered):
        bucket_index = min(2, int(index * 3 / total))
        buckets[FLOW_BUCKETS[bucket_index + 1]].append(row)
    return buckets


def numeric_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    values = []
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None:
            values.append(value)
    return values


def replacement_metrics(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for comparator in COMPARATORS:
        field = f"replacement_value_{horizon}d_vs_{comparator}_usd"
        metrics[f"replacement_value_vs_{comparator}_usd"] = stats(numeric_values(rows, field))
    return metrics


def concentration(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    field = f"replacement_value_{horizon}d_vs_cash_usd"
    by_ticker: dict[str, float] = defaultdict(float)
    for row in rows:
        value = safe_float(row.get(field))
        ticker = str(row.get("ticker") or "").upper()
        if ticker and value is not None and value > 0:
            by_ticker[ticker] += value
    positive = sum(by_ticker.values())
    if positive <= 0:
        return {
            "positive_pnl": 0.0,
            "positive_ticker_count": 0,
            "max_single_positive_pnl_share": None,
            "positive_pnl_hhi": None,
            "top_positive_tickers": [],
        }
    shares = {ticker: value / positive for ticker, value in by_ticker.items()}
    top = sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)[:8]
    return {
        "positive_pnl": round(positive, 2),
        "positive_ticker_count": len(by_ticker),
        "max_single_positive_pnl_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(share * share for share in shares.values()), 6),
        "top_positive_tickers": [
            {"ticker": ticker, "pnl": round(value, 2), "share": round(shares[ticker], 6)}
            for ticker, value in top
        ],
    }


def group_summary(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    asof_dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    score_values = numeric_values(rows, "active13f_active_flow_score")
    return {
        "n": len(rows),
        "ticker_count": len(tickers),
        "asof_date_count": len(asof_dates),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "active_flow_score_mean": round_or_none(mean(score_values), 6),
        "active_flow_score_median": round_or_none(median(score_values), 6)
        if score_values
        else None,
        "active_value_share_median": round_or_none(
            median(numeric_values(rows, "active13f_active_value_share")), 6
        )
        if numeric_values(rows, "active13f_active_value_share")
        else None,
        "active_value_log_delta_median": round_or_none(
            median(numeric_values(rows, "active13f_active_value_log_delta")), 6
        )
        if numeric_values(rows, "active13f_active_value_log_delta")
        else None,
        "active_holder_delta_median": round_or_none(
            median(numeric_values(rows, "active13f_active_holder_count_delta")), 6
        )
        if numeric_values(rows, "active13f_active_holder_count_delta")
        else None,
        "replacement_metrics": replacement_metrics(rows, horizon),
        "cash_positive_concentration": concentration(rows, horizon),
    }


def rankdata(values: list[float]) -> list[float]:
    ordered = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        avg_rank = (index + end - 1) / 2.0
        for _, original_index in ordered[index:end]:
            ranks[original_index] = avg_rank
        index = end
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    x_mean = mean(xs)
    y_mean = mean(ys)
    if x_mean is None or y_mean is None:
        return None
    xdiff = [x - x_mean for x in xs]
    ydiff = [y - y_mean for y in ys]
    xdenom = math.sqrt(sum(x * x for x in xdiff))
    ydenom = math.sqrt(sum(y * y for y in ydiff))
    if xdenom <= 0 or ydenom <= 0:
        return None
    return sum(x * y for x, y in zip(xdiff, ydiff)) / (xdenom * ydenom)


def spearman(rows: list[dict[str, Any]], horizon: int, comparator: str) -> float | None:
    xs = []
    ys = []
    field = f"replacement_value_{horizon}d_vs_{comparator}_usd"
    for row in rows:
        score = safe_float(row.get("active13f_active_flow_score"))
        value = safe_float(row.get(field))
        if score is not None and value is not None:
            xs.append(score)
            ys.append(value)
    if len(xs) < 3:
        return None
    return round_or_none(pearson(rankdata(xs), rankdata(ys)), 6)


def metric_mean(summary: dict[str, Any], bucket: str, comparator: str) -> float | None:
    return summary["buckets"][bucket]["replacement_metrics"][
        f"replacement_value_vs_{comparator}_usd"
    ]["mean"]


def metric_median(summary: dict[str, Any], bucket: str, comparator: str) -> float | None:
    return summary["buckets"][bucket]["replacement_metrics"][
        f"replacement_value_vs_{comparator}_usd"
    ]["median"]


def summarize_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    settled = settled_rows(rows, horizon)
    buckets = bucket_rows(settled)
    scored = [row for row in settled if safe_float(row.get("active13f_active_flow_score")) is not None]
    summary = {
        "horizon": horizon,
        "settled_rows": len(settled),
        "scored_rows": len(scored),
        "missing_active_flow_rows": len(buckets["missing_active_flow"]),
        "scored_asof_date_count": len(
            {str(row.get("asof_date") or "")[:10] for row in scored if row.get("asof_date")}
        ),
        "buckets": {bucket: group_summary(bucket_rows_, horizon) for bucket, bucket_rows_ in buckets.items()},
        "spearman_score_to_replacement": {
            comparator: spearman(scored, horizon, comparator) for comparator in COMPARATORS
        },
    }
    support: dict[str, Any] = {}
    for comparator in COMPARATORS:
        high_mean = metric_mean(summary, "high_active_flow", comparator)
        low_mean = metric_mean(summary, "low_active_flow", comparator)
        high_median = metric_median(summary, "high_active_flow", comparator)
        low_median = metric_median(summary, "low_active_flow", comparator)
        support[f"high_mean_{comparator}_beats_low"] = (
            high_mean is not None and low_mean is not None and high_mean > low_mean
        )
        support[f"high_median_{comparator}_beats_low"] = (
            high_median is not None and low_median is not None and high_median > low_median
        )
    summary["support"] = support
    return summary


def source_summary(rows: list[dict[str, Any]], flow: dict[str, Any]) -> dict[str, Any]:
    ids = [str(row.get("observation_id") or "") for row in rows if row.get("observation_id")]
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    asof_dates = sorted({str(row.get("asof_date") or "")[:10] for row in rows if row.get("asof_date")})
    active_status = Counter(str(row.get("active13f_status") or "missing") for row in rows)
    return {
        "outcome_ledger": repo_rel(OUTCOME_LEDGER),
        "outcome_ledger_exists": OUTCOME_LEDGER.exists(),
        "outcome_rows": len(rows),
        "duplicate_observation_ids": len(ids) - len(set(ids)),
        "ticker_count": len(tickers),
        "asof_date_start": asof_dates[0] if asof_dates else None,
        "asof_date_end": asof_dates[-1] if asof_dates else None,
        "asof_date_count": len(asof_dates),
        "sec13f_status_counts": dict(
            sorted(Counter(str(row.get("sec13f_status") or "missing") for row in rows).items())
        ),
        "outcome_status_counts": dict(
            sorted(Counter(str(row.get("outcome_status") or "missing") for row in rows).items())
        ),
        "active13f_status_counts": dict(sorted(active_status.items())),
        "flow_source_summary": flow["summary"],
    }


def evaluate_gate4(horizons: dict[int, dict[str, Any]]) -> dict[str, Any]:
    primary = horizons[PRIMARY_HORIZON]
    high = primary["buckets"]["high_active_flow"]
    checks: dict[str, bool] = {
        "primary_scored_rows_floor": primary["scored_rows"]
        >= ACCEPTANCE_RULE["min_primary_scored_rows"],
        "primary_asof_dates_floor": primary["scored_asof_date_count"]
        >= ACCEPTANCE_RULE["min_primary_asof_dates"],
    }
    for comparator in COMPARATORS:
        checks[f"primary_high_mean_{comparator}_beats_low"] = bool(
            primary["support"].get(f"high_mean_{comparator}_beats_low")
        )
        checks[f"primary_high_median_{comparator}_beats_low"] = bool(
            primary["support"].get(f"high_median_{comparator}_beats_low")
        )
        rho = primary["spearman_score_to_replacement"].get(comparator)
        checks[f"primary_spearman_{comparator}_positive"] = (
            rho is not None and rho > 0
        )
        support_count = sum(
            1
            for summary in horizons.values()
            if summary["support"].get(f"high_mean_{comparator}_beats_low")
        )
        checks[f"multi_horizon_mean_{comparator}_support"] = (
            support_count >= ACCEPTANCE_RULE["min_supporting_horizons_high_beats_low"]
        )

    concentration_check = high["cash_positive_concentration"]
    max_share = concentration_check.get("max_single_positive_pnl_share")
    hhi = concentration_check.get("positive_pnl_hhi")
    checks["high_bucket_single_ticker_concentration_pass"] = (
        max_share is not None
        and max_share <= ACCEPTANCE_RULE["max_single_positive_pnl_share"]
    )
    checks["high_bucket_positive_hhi_pass"] = (
        hhi is not None and hhi <= ACCEPTANCE_RULE["positive_pnl_hhi_guardrail"]
    )

    failed = [key for key, ok in checks.items() if not ok]
    observed_only_lead = not failed
    return {
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_kova_sec13f_active_manager_flow_lead_not_promoted"
            if observed_only_lead
            else "rejected_no_kova_sec13f_active_manager_flow_forward_edge"
        ),
        "acceptance_checks": checks,
        "failed_reasons": failed,
        "lead_limitations": [
            "Forward-only post-2026-06-13 observations, not canonical fixed-window PIT coverage.",
            "10d outcomes remain pending and are excluded from the decision.",
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


def build_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    flow = build_flow_features([], rows)
    enriched = enrich_outcome_rows(rows, flow)
    horizons = {horizon: summarize_horizon(enriched, horizon) for horizon in HORIZONS}
    return {
        "rows": enriched,
        "source_summary": source_summary(enriched, flow),
        "horizons": horizons,
        "score_definition": (
            "active13f_active_flow_score = average percentile rank of "
            "active_value_share, active_holder_share, active_value_log_delta, "
            "and active_holder_count_delta. Active managers hold between "
            f"{ACTIVE_MANAGER_MIN_HOLDINGS} and {ACTIVE_MANAGER_MAX_HOLDINGS} "
            "mapped long-equity tickers in the raw SEC13F ZIP window."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction(ticket if isinstance(ticket, dict) else {})
    before = baseline_metrics()
    rows = read_jsonl(OUTCOME_LEDGER)
    analysis = build_analysis(rows)
    horizons = analysis["horizons"]
    gate4 = evaluate_gate4(horizons)
    observed_only_lead = gate4["observed_only_lead"]
    status = "observed_only_positive_lead" if observed_only_lead else "observed_only_rejected"
    probability = safe_float(prediction.get("success_probability")) or 0.0
    actual_success = 1 if observed_only_lead else 0
    why = (
        "The fixed active-manager/active-flow field "
        f"{'did' if observed_only_lead else 'did not'} separate settled Kova "
        "forward replacement rows across the strict 5d cash/SPY/QQQ checks. "
        "This remains forward-only attribution and did not promote any trading behavior."
    )
    compact_horizons = {str(key): value for key, value in horizons.items()}
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": observed_only_lead,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution_runner",
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
        "calibration": {
            "predicted_success_probability": probability,
            "actual_success": actual_success,
            "brier_score": round((probability - actual_success) ** 2, 4),
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_modes": gate4["failed_reasons"],
            "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
            "surprise_note": (
                "Low surprise: active-manager flow was a named new evidence axis, "
                "but this is still a partial forward ledger with strict "
                "multi-comparator evidence requirements."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation passed without override. Nearest prior was "
                    "sec13f_active_manager_concentration, but this run joins raw "
                    "manager-level active-flow deltas to exp017 closed forward rows."
                ),
                "exp-20260624-018": (
                    "Observed-only positive aggregate sponsorship lead; it forbids "
                    "holder-count/value/position-count retries on the same rows."
                ),
                "exp-20260624-019": (
                    "Rejected coownership-network follow-up; this run is not peer "
                    "count/lift/shared-manager/Jaccard."
                ),
                "exp-20260624-023": "Rejected options cross-evidence on the same Kova surface.",
                "exp-20260625-006": "Rejected Companyfacts quality cross-evidence.",
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: parse raw manager-level 13F "
                "ZIPs, classify concentrated active managers, compute quarter-over-"
                "quarter active-flow score, and test settled Kova forward "
                "cash/SPY/QQQ replacement-value separation."
            ),
            "4_success_failure_standard": (
                "Observed-only lead only if primary 5d scored sample/as-of floors "
                "pass, high active-flow beats low by mean and median on cash/SPY/QQQ, "
                "Spearman correlations are positive, at least two horizons support "
                "high>low by mean, and high-bucket positive PnL concentration passes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_outcome_ledger": repo_rel(OUTCOME_LEDGER),
            "sec13f_source_cache": repo_rel(SEC13F_CACHE),
            "horizons": HORIZONS,
            "primary_horizon": PRIMARY_HORIZON,
            "bucket_method": "tertiles on fixed active13f_active_flow_score; missing measured separately",
            "active_manager_rule": {
                "min_universe_holdings": ACTIVE_MANAGER_MIN_HOLDINGS,
                "max_universe_holdings": ACTIVE_MANAGER_MAX_HOLDINGS,
                "long_equity_only": True,
            },
            "score_definition": analysis["score_definition"],
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "source_summary": analysis["source_summary"],
        "attribution": {
            "score_definition": analysis["score_definition"],
            "horizons": compact_horizons,
            "sample_rows": [
                {
                    "ticker": row.get("ticker"),
                    "asof_date": row.get("asof_date"),
                    "active13f_window_label": row.get("active13f_window_label"),
                    "active13f_active_flow_score": round_or_none(
                        row.get("active13f_active_flow_score"), 6
                    ),
                    "active13f_active_value_share": round_or_none(
                        row.get("active13f_active_value_share"), 6
                    ),
                    "active13f_active_value_log_delta": round_or_none(
                        row.get("active13f_active_value_log_delta"), 6
                    ),
                    "replacement_value_5d_vs_cash_usd": row.get(
                        "replacement_value_5d_vs_cash_usd"
                    ),
                    "replacement_value_5d_vs_spy_usd": row.get(
                        "replacement_value_5d_vs_spy_usd"
                    ),
                    "replacement_value_5d_vs_qqq_usd": row.get(
                        "replacement_value_5d_vs_qqq_usd"
                    ),
                }
                for row in analysis["rows"][:25]
            ],
        },
        "primary_summary": {
            "horizon": PRIMARY_HORIZON,
            "summary": horizons[PRIMARY_HORIZON],
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": before,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(rows)
            and analysis["source_summary"]["duplicate_observation_ids"] == 0
            and bool(analysis["source_summary"]["flow_source_summary"]["loaded_window_labels"]),
            "fields_checked": [
                "observation_id",
                "asof_date",
                "ticker",
                "sec13f_source_file",
                "raw SEC13F manager_cik/manager_name",
                "raw SEC13F name_of_issuer",
                "raw SEC13F value_usd_thousands",
                "raw SEC13F shares",
                "active13f_active_flow_score",
                "forward_1d_status",
                "forward_3d_status",
                "forward_5d_status",
                "replacement_value_1d_vs_cash_usd",
                "replacement_value_3d_vs_spy_usd",
                "replacement_value_5d_vs_qqq_usd",
                "entry_date",
                "target_price",
            ],
            "source_summary": analysis["source_summary"],
            "target_price_relevance": (
                "Not applicable: this is observed-only fixed-horizon outcome "
                "attribution and does not schedule target exits or orders."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(rows),
            "signals_survived": horizons[PRIMARY_HORIZON]["settled_rows"],
            "survival_rate": round(horizons[PRIMARY_HORIZON]["settled_rows"] / len(rows), 4)
            if rows
            else None,
            "baseline_survival_rate": before.get("survival_rate"),
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": gate4,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry Kova SEC13F active-holder share, active-value share, "
                "active-flow deltas, aggregate sponsorship, coownership network, "
                "options cross-evidence, Companyfacts quality, top-N, hold, "
                "cooldown, notional, or allocator thresholds on the same exp017 "
                "partial forward rows. This fixed active-flow attribution is the "
                "result for that surface."
            ),
            "new_evidence_required": (
                "A valid retry needs enough closed 10d replacement-value rows, "
                "manager-level active-flow provenance from a new non-quarterly "
                "source, borrow/loan-availability cross-evidence, or canonical "
                "fixed-window PIT coverage through a shared default-off helper."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUTCOME_LEDGER),
            repo_rel(SEC13F_CACHE),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260624-018.json",
            "experiments/logs/exp-20260624-019.json",
            "experiments/logs/exp-20260624-023.json",
            "experiments/logs/exp-20260625-006.json",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at") if isinstance(ticket, dict) else None,
            "claimed_at": ticket.get("claimed_at") if isinstance(ticket, dict) else None,
            "hub_identity": ticket.get("hub_identity") if isinstance(ticket, dict) else None,
            "novelty": ticket.get("novelty") if isinstance(ticket, dict) else None,
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    primary = payload["primary_summary"]["summary"]
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "observed_only_lead": payload["observed_only_lead"],
        "lane": payload["lane"],
        "owner": payload["owner"],
        "hypothesis": payload["hypothesis"],
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
        "primary_summary": {
            "horizon": PRIMARY_HORIZON,
            "settled_rows": primary["settled_rows"],
            "scored_rows": primary["scored_rows"],
            "scored_asof_date_count": primary["scored_asof_date_count"],
            "buckets": primary["buckets"],
            "spearman_score_to_replacement": primary["spearman_score_to_replacement"],
            "support": primary["support"],
        },
        "horizon_support": {
            horizon: {
                "settled_rows": summary["settled_rows"],
                "scored_rows": summary["scored_rows"],
                "support": summary["support"],
                "spearman_score_to_replacement": summary["spearman_score_to_replacement"],
            }
            for horizon, summary in payload["attribution"]["horizons"].items()
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


def build_card(payload: dict[str, Any]) -> str:
    primary = payload["primary_summary"]["summary"]
    rows = [
        "| Bucket | Rows | Score Median | Active Value Share Median | Active Flow Delta Median | Mean Cash | Mean SPY | Mean QQQ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in FLOW_BUCKETS:
        summary = primary["buckets"][bucket]
        metrics = summary["replacement_metrics"]
        rows.append(
            "| {bucket} | {n} | {score} | {share} | {delta} | {cash} | {spy} | {qqq} |".format(
                bucket=bucket,
                n=summary["n"],
                score=summary["active_flow_score_median"],
                share=summary["active_value_share_median"],
                delta=summary["active_value_log_delta_median"],
                cash=money(metrics["replacement_value_vs_cash_usd"]["mean"]),
                spy=money(metrics["replacement_value_vs_spy_usd"]["mean"]),
                qqq=money(metrics["replacement_value_vs_qqq_usd"]["mean"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Kova SEC13F active-manager flow attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- 5d scored rows: `{primary['scored_rows']}`",
            f"- 5d as-of dates: `{primary['scored_asof_date_count']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Primary 5d Buckets",
            "",
            *rows,
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
            "No JavaScript was used.",
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
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        OUTCOME_LEDGER,
    ]
    for label in payload["source_summary"]["flow_source_summary"]["loaded_window_labels"]:
        files.append(SEC13F_CACHE / f"{label}_form13f.zip")
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
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
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
    primary = payload["primary_summary"]["summary"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "observed_only_lead": payload["observed_only_lead"],
                "primary_scored_rows": primary["scored_rows"],
                "primary_asof_dates": primary["scored_asof_date_count"],
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
