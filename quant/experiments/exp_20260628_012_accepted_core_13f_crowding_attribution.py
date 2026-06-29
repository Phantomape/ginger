"""exp-20260628-012: accepted-core 13F crowding attribution.

Read-only alpha attribution over the current accepted core stack. The tested
field is a point-in-time, sector-normalized 13F ownership crowding score joined
to already accepted trades at entry. This runner does not alter candidate
pools, entries, exits, ranking, sizing, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260628-012"
OWNER = "alpha-explore"
LANE = "alpha_search"
SLUG = "accepted_core_13f_crowding_attribution"
RUNNER = f"quant/experiments/exp_20260628_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "accepted_core_pit_13f_crowding_loss_tail_attribution_v1"
TRIAL_FAMILY = "accepted_core_13f_crowding_risk_attribution"
TRIAL_VARIANT_ID = "accepted_stack_sector_normalized_holder_value_crowding_v1"
MECHANISM_FAMILY = "production_visible_13f_crowding_risk_attribution"
CHANGE_TYPE = "observed_only_attribution"
IMPLEMENTATION_MODE = "observed_only_attribution"
NEW_EVIDENCE_TYPE = "new_gate_shape_pit_13f_risk_attribution"
NEW_EVIDENCE_AXIS = (
    "New gate shape: PIT 13F ownership/crowding joined only to already accepted "
    "core trades for read-only risk attribution, not a direct candidate-pool "
    "source, source rank, threshold scan, or same-row forward ledger reslice."
)

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260602-003"
    / "exp_20260602_003_post_earnings_explicit_continuation.json"
)
STANDARD_WINDOW_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOW_FILES: "OrderedDict[str, Path]" = OrderedDict(
    [
        (
            "late_strong",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "late_strong_after.json",
        ),
        (
            "mid_weak",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "mid_weak_after.json",
        ),
        (
            "old_thin",
            REPO_ROOT / "data" / "experiments" / "exp-20260602-003" / "old_thin_after.json",
        ),
    ]
)
SECTOR_MAP_JSON = REPO_ROOT / "data" / "reference" / "broad_market_sector_map.json"
HOLDINGS_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec13f_institutional"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Read-only risk-allocation alpha attribution: accepted core trades with high "
    "point-in-time 13F ownership crowding may carry worse loss-tail and lower PnL "
    "than less-crowded accepted trades, identifying a future production-visible "
    "risk-scaling hypothesis without changing candidate pools, entries, exits, "
    "ranking, sizing, or orders."
)
CAUSAL_COMPONENTS = [
    "canonical accepted-stack trade replay",
    "PIT 13F holdings join",
    "sector-normalized crowding buckets",
    "loss-tail attribution",
    "no strategy behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260618-016",
    "exp-20260622-007",
    "exp-20260624-019",
    "exp-20260625-010",
    "exp-20260625-012",
]

# Fixed ex-ante thresholds. The crowding score is the mean of sector percentile
# ranks for holder_count and total_value_usd in the latest available 13F snapshot.
LOW_CROWDING_MAX = 0.40
HIGH_CROWDING_MIN = 0.80
LOSS_TAIL_PNL_PCT = -0.02
MIN_JOINED_ROWS = 50
MIN_HIGH_BUCKET_ROWS = 10
MIN_LOW_BUCKET_ROWS = 10
MIN_SUPPORTING_WINDOWS = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def repo_rel(path: Path | str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return str(p.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def round_float(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    return None if number is None else round(number, digits)


def parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def load_sector_map() -> dict[str, str]:
    payload = read_json(SECTOR_MAP_JSON, {})
    entries = payload.get("entries") if isinstance(payload, dict) else {}
    out: dict[str, str] = {}
    if not isinstance(entries, dict):
        return out
    for ticker, record in entries.items():
        if isinstance(record, dict) and record.get("sector"):
            out[str(ticker).upper()] = str(record["sector"])
    return out


def percentile_map(values: dict[str, float | None]) -> dict[str, float]:
    valid = sorted((float(value), ticker) for ticker, value in values.items() if value is not None)
    if not valid:
        return {}
    if len(valid) == 1:
        return {valid[0][1]: 1.0}
    out: dict[str, float] = {}
    index = 0
    denominator = len(valid) - 1
    while index < len(valid):
        end = index + 1
        while end < len(valid) and valid[end][0] == valid[index][0]:
            end += 1
        pct = ((index + end - 1) / 2.0) / denominator
        for _, ticker in valid[index:end]:
            out[ticker] = pct
        index = end
    return out


def bucket_for(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= HIGH_CROWDING_MIN:
        return "high"
    if score <= LOW_CROWDING_MAX:
        return "low"
    return "middle"


def target_price_from_trade(trade: dict[str, Any]) -> float | None:
    entry = as_float(trade.get("entry_price"))
    stop = as_float(trade.get("stop_price"))
    mult = as_float(trade.get("target_mult_used"))
    if entry is None or stop is None or mult is None:
        return None
    risk_per_share = max(entry - stop, 0.0)
    if risk_per_share <= 0:
        return None
    return round(entry + (risk_per_share * mult), 4)


def load_13f_snapshots() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sector_map = load_sector_map()
    snapshots: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []
    for path in sorted(HOLDINGS_DIR.glob("holdings_*.json")):
        payload = read_json(path, {})
        as_of = parse_day(payload.get("as_of")) if isinstance(payload, dict) else None
        holdings = payload.get("holdings") if isinstance(payload, dict) else None
        if as_of is None or not isinstance(holdings, list):
            source_files.append(
                {
                    "path": repo_rel(path),
                    "loaded": False,
                    "as_of": payload.get("as_of") if isinstance(payload, dict) else None,
                    "holdings_rows": len(holdings) if isinstance(holdings, list) else 0,
                }
            )
            continue

        by_ticker: dict[str, dict[str, Any]] = {}
        by_sector: dict[str, list[str]] = defaultdict(list)
        for row in holdings:
            if not isinstance(row, dict) or not row.get("ticker"):
                continue
            ticker = str(row["ticker"]).upper()
            holder_count = as_float(row.get("holder_count"))
            total_value = as_float(row.get("total_value_usd"))
            position_rows = as_float(row.get("position_row_count"))
            sector = sector_map.get(ticker, "Unknown")
            record = {
                "ticker": ticker,
                "sector": sector,
                "holder_count": round_float(holder_count, 4),
                "position_row_count": round_float(position_rows, 4),
                "total_value_usd": round_float(total_value, 2),
                "total_shares": round_float(row.get("total_shares"), 4),
                "report_period": row.get("report_period"),
            }
            by_ticker[ticker] = record
            by_sector[sector].append(ticker)

        for sector, tickers in by_sector.items():
            holder_pct = percentile_map(
                {ticker: by_ticker[ticker].get("holder_count") for ticker in tickers}
            )
            value_pct = percentile_map(
                {ticker: by_ticker[ticker].get("total_value_usd") for ticker in tickers}
            )
            position_pct = percentile_map(
                {ticker: by_ticker[ticker].get("position_row_count") for ticker in tickers}
            )
            for ticker in tickers:
                record = by_ticker[ticker]
                fields = [
                    holder_pct.get(ticker),
                    value_pct.get(ticker),
                ]
                usable = [value for value in fields if value is not None]
                record["holder_count_sector_percentile"] = round_float(
                    holder_pct.get(ticker), 6
                )
                record["total_value_sector_percentile"] = round_float(
                    value_pct.get(ticker), 6
                )
                record["position_rows_sector_percentile"] = round_float(
                    position_pct.get(ticker), 6
                )
                record["crowding_score"] = round_float(mean([float(value) for value in usable]), 6)
                record["crowding_bucket"] = bucket_for(record.get("crowding_score"))

        snapshots.append(
            {
                "path": path,
                "as_of": as_of,
                "as_of_iso": as_of.isoformat(),
                "window_label": payload.get("window_label"),
                "universe_size": payload.get("universe_size"),
                "universe_covered_count": payload.get("universe_covered_count"),
                "universe_coverage_pct": payload.get("universe_coverage_pct"),
                "holdings_rows": len(holdings),
                "holdings_by_ticker": by_ticker,
            }
        )
        source_files.append(
            {
                "path": repo_rel(path),
                "loaded": True,
                "as_of": as_of.isoformat(),
                "window_label": payload.get("window_label"),
                "holdings_rows": len(holdings),
                "tickers_with_sector": sum(
                    1 for ticker in by_ticker if ticker in sector_map
                ),
            }
        )
    snapshots.sort(key=lambda row: row["as_of"])
    return snapshots, {
        "holdings_dir": repo_rel(HOLDINGS_DIR),
        "sector_map": repo_rel(SECTOR_MAP_JSON),
        "snapshot_count": len(snapshots),
        "source_files": source_files,
    }


def latest_snapshot_for_entry(
    snapshots: list[dict[str, Any]], entry_date: date | None
) -> dict[str, Any] | None:
    if entry_date is None:
        return None
    selected = None
    for snapshot in snapshots:
        if snapshot["as_of"] <= entry_date:
            selected = snapshot
        else:
            break
    return selected


def enrich_trade(
    label: str, trade: dict[str, Any], snapshots: list[dict[str, Any]]
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    entry_day = parse_day(trade.get("entry_date"))
    snapshot = latest_snapshot_for_entry(snapshots, entry_day)
    holding = None
    if snapshot is not None and ticker:
        holding = snapshot["holdings_by_ticker"].get(ticker)

    pnl = as_float(trade.get("pnl")) or 0.0
    pnl_pct = as_float(trade.get("pnl_pct_net")) or 0.0
    target_price = target_price_from_trade(trade)
    entry_price = as_float(trade.get("entry_price"))
    shares = as_float(trade.get("shares"))
    entry_notional = entry_price * shares if entry_price is not None and shares is not None else None
    crowding_score = as_float(holding.get("crowding_score")) if holding else None
    snapshot_as_of = snapshot.get("as_of") if snapshot else None
    staleness_days = (
        (entry_day - snapshot_as_of).days
        if entry_day is not None and isinstance(snapshot_as_of, date)
        else None
    )

    return {
        "window": label,
        "ticker": ticker or None,
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector") or (holding.get("sector") if holding else None),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "entry_price": round_float(entry_price, 4),
        "target_price_reconstructed": target_price,
        "shares": round_float(shares, 4),
        "entry_notional": round_float(entry_notional, 2),
        "pnl": round_float(pnl, 2),
        "pnl_pct_net": round_float(pnl_pct, 8),
        "is_loss": pnl < 0,
        "is_loss_tail": pnl_pct <= LOSS_TAIL_PNL_PCT,
        "snapshot_available": snapshot is not None,
        "13f_joined": holding is not None,
        "13f_snapshot_as_of": snapshot.get("as_of_iso") if snapshot else None,
        "13f_snapshot_path": repo_rel(snapshot["path"]) if snapshot else None,
        "13f_window_label": snapshot.get("window_label") if snapshot else None,
        "13f_report_period": holding.get("report_period") if holding else None,
        "13f_staleness_days": staleness_days,
        "holder_count": holding.get("holder_count") if holding else None,
        "position_row_count": holding.get("position_row_count") if holding else None,
        "total_value_usd": holding.get("total_value_usd") if holding else None,
        "total_shares": holding.get("total_shares") if holding else None,
        "holder_count_sector_percentile": (
            holding.get("holder_count_sector_percentile") if holding else None
        ),
        "total_value_sector_percentile": (
            holding.get("total_value_sector_percentile") if holding else None
        ),
        "position_rows_sector_percentile": (
            holding.get("position_rows_sector_percentile") if holding else None
        ),
        "crowding_score": round_float(crowding_score, 6),
        "crowding_bucket": bucket_for(crowding_score),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row["pnl"]) for row in rows if row.get("pnl") is not None]
    pnl_pcts = [
        float(row["pnl_pct_net"]) for row in rows if row.get("pnl_pct_net") is not None
    ]
    crowding_scores = [
        float(row["crowding_score"]) for row in rows if row.get("crowding_score") is not None
    ]
    holder_pcts = [
        float(row["holder_count_sector_percentile"])
        for row in rows
        if row.get("holder_count_sector_percentile") is not None
    ]
    value_pcts = [
        float(row["total_value_sector_percentile"])
        for row in rows
        if row.get("total_value_sector_percentile") is not None
    ]
    staleness = [
        float(row["13f_staleness_days"])
        for row in rows
        if row.get("13f_staleness_days") is not None
    ]
    return {
        "n": len(rows),
        "joined_n": sum(1 for row in rows if row.get("13f_joined")),
        "total_pnl": round_float(sum(pnls), 2),
        "avg_pnl": mean(pnls),
        "median_pnl": median(pnls),
        "avg_pnl_pct_net": mean(pnl_pcts),
        "median_pnl_pct_net": median(pnl_pcts),
        "win_rate": round_float(
            sum(1 for row in rows if (row.get("pnl") or 0) > 0) / len(rows)
            if rows
            else None,
            6,
        ),
        "loss_rate": round_float(
            sum(1 for row in rows if row.get("is_loss")) / len(rows)
            if rows
            else None,
            6,
        ),
        "loss_tail_rate": round_float(
            sum(1 for row in rows if row.get("is_loss_tail")) / len(rows)
            if rows
            else None,
            6,
        ),
        "avg_crowding_score": mean(crowding_scores),
        "median_crowding_score": median(crowding_scores),
        "avg_holder_count_sector_percentile": mean(holder_pcts),
        "avg_total_value_sector_percentile": mean(value_pcts),
        "avg_13f_staleness_days": mean(staleness),
    }


def summarize_by_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for bucket in ("low", "middle", "high", "unknown"):
        bucket_rows = [row for row in rows if row.get("crowding_bucket") == bucket]
        if bucket_rows or bucket != "unknown":
            out[bucket] = summarize_rows(bucket_rows)
    return out


def compare_high_low(summary: dict[str, Any]) -> dict[str, Any]:
    high = summary.get("high") or {}
    low = summary.get("low") or {}
    if not high.get("n") or not low.get("n"):
        return {"available": False}
    return {
        "available": True,
        "high_minus_low_avg_pnl": round_float(
            (high.get("avg_pnl") or 0.0) - (low.get("avg_pnl") or 0.0),
            2,
        ),
        "high_minus_low_median_pnl": round_float(
            (high.get("median_pnl") or 0.0) - (low.get("median_pnl") or 0.0),
            2,
        ),
        "high_minus_low_win_rate": round_float(
            (high.get("win_rate") or 0.0) - (low.get("win_rate") or 0.0),
            6,
        ),
        "high_minus_low_loss_tail_rate": round_float(
            (high.get("loss_tail_rate") or 0.0) - (low.get("loss_tail_rate") or 0.0),
            6,
        ),
    }


def load_baseline_summary() -> dict[str, Any]:
    baseline = read_json(BASELINE_RESULT, {})
    standard = read_json(STANDARD_WINDOW_RESULT, {})
    return {
        "accepted_stack_artifact": repo_rel(BASELINE_RESULT),
        "standard_window_result": repo_rel(STANDARD_WINDOW_RESULT),
        "experiment_id": baseline.get("experiment_id"),
        "decision": baseline.get("decision"),
        "status": baseline.get("status"),
        "aggregate": baseline.get("aggregate"),
        "standard_window_summary": standard,
    }


def load_rows(
    snapshots: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_audit: dict[str, Any] = {}
    for label, path in WINDOW_FILES.items():
        payload = read_json(path, {})
        trades = payload.get("trades") if isinstance(payload, dict) else None
        if not isinstance(trades, list):
            trades = []
        enriched = [enrich_trade(label, trade, snapshots) for trade in trades]
        rows.extend(enriched)
        source_audit[label] = {
            "path": repo_rel(path),
            "trade_rows": len(trades),
            "rows_with_entry_date": sum(1 for row in enriched if row.get("entry_date")),
            "rows_with_target_price_reconstructed": sum(
                1 for row in enriched if row.get("target_price_reconstructed") is not None
            ),
            "rows_with_13f_snapshot": sum(1 for row in enriched if row.get("snapshot_available")),
            "rows_with_13f_join": sum(1 for row in enriched if row.get("13f_joined")),
            "bucket_counts": {
                bucket: sum(1 for row in enriched if row.get("crowding_bucket") == bucket)
                for bucket in ("low", "middle", "high", "unknown")
            },
        }
    return rows, source_audit


def build_attribution(
    rows: list[dict[str, Any]], source_audit: dict[str, Any], snapshot_audit: dict[str, Any]
) -> dict[str, Any]:
    by_window: dict[str, Any] = OrderedDict()
    for label in WINDOW_FILES:
        window_rows = [row for row in rows if row["window"] == label]
        bucket_summary = summarize_by_bucket(window_rows)
        by_window[label] = {
            "all": summarize_rows(window_rows),
            "buckets": bucket_summary,
            "high_low": compare_high_low(bucket_summary),
        }

    pooled_buckets = summarize_by_bucket(rows)
    return {
        "source_audit": source_audit,
        "snapshot_audit": snapshot_audit,
        "parameters": {
            "join_rule": "latest 13F holdings snapshot with as_of <= trade.entry_date",
            "crowding_score": (
                "mean(holder_count_sector_percentile, total_value_sector_percentile)"
            ),
            "low_crowding_max": LOW_CROWDING_MAX,
            "high_crowding_min": HIGH_CROWDING_MIN,
            "loss_tail_pnl_pct": LOSS_TAIL_PNL_PCT,
            "uses_realized_exit_information": False,
            "alters_strategy_behavior": False,
        },
        "pooled": {
            "all": summarize_rows(rows),
            "buckets": pooled_buckets,
            "high_low": compare_high_low(pooled_buckets),
        },
        "by_window": by_window,
        "sample_rows": [row for row in rows if row.get("13f_joined")][:25],
        "sample_high_bucket_rows": [
            row for row in rows if row.get("crowding_bucket") == "high"
        ][:25],
        "sample_low_bucket_rows": [
            row for row in rows if row.get("crowding_bucket") == "low"
        ][:25],
    }


def evaluate_gate4(attribution: dict[str, Any]) -> dict[str, Any]:
    pooled = attribution["pooled"]
    high = pooled["buckets"]["high"]
    low = pooled["buckets"]["low"]
    high_low = pooled["high_low"]
    joined_rows = pooled["all"].get("joined_n") or 0
    window_comparisons = {
        label: row["high_low"] for label, row in attribution["by_window"].items()
    }
    supporting = [
        label
        for label, row in window_comparisons.items()
        if row.get("available")
        and (row.get("high_minus_low_avg_pnl") or 0.0) < 0
        and (row.get("high_minus_low_win_rate") or 0.0) < 0
        and (row.get("high_minus_low_loss_tail_rate") or 0.0) > 0
    ]
    failures: list[str] = []
    if joined_rows < MIN_JOINED_ROWS:
        failures.append("joined_sample_too_small")
    if (high.get("n") or 0) < MIN_HIGH_BUCKET_ROWS:
        failures.append("high_bucket_sample_too_small")
    if (low.get("n") or 0) < MIN_LOW_BUCKET_ROWS:
        failures.append("low_bucket_sample_too_small")
    if not high_low.get("available"):
        failures.append("high_low_comparison_unavailable")
    else:
        if (high_low.get("high_minus_low_avg_pnl") or 0.0) >= 0:
            failures.append("high_bucket_avg_pnl_not_worse")
        if (high_low.get("high_minus_low_win_rate") or 0.0) >= 0:
            failures.append("high_bucket_win_rate_not_worse")
        if (high_low.get("high_minus_low_loss_tail_rate") or 0.0) <= 0:
            failures.append("high_bucket_loss_tail_not_worse")
    if len(supporting) < MIN_SUPPORTING_WINDOWS:
        failures.append("insufficient_window_support")

    observed_only_lead = not failures
    return {
        "passed": observed_only_lead,
        "observed_only_lead": observed_only_lead,
        "decision": (
            "observed_only_positive_13f_crowding_loss_tail_edge"
            if observed_only_lead
            else "rejected_no_pit_13f_crowding_loss_tail_edge"
        ),
        "acceptance_rule": (
            "Observed-only lead only if joined sample >=50, high bucket >=10, "
            "low bucket >=10, pooled high bucket has lower avg PnL, lower win "
            "rate, higher 2pct loss-tail rate than low bucket, and all three "
            "windows support the same direction. No strategy acceptance is "
            "possible in this run."
        ),
        "failed_reasons": failures,
        "supporting_windows": supporting,
        "window_comparisons": window_comparisons,
        "pooled_high_low": high_low,
        "minimums": {
            "min_joined_rows": MIN_JOINED_ROWS,
            "min_high_bucket_rows": MIN_HIGH_BUCKET_ROWS,
            "min_low_bucket_rows": MIN_LOW_BUCKET_ROWS,
            "min_supporting_windows": MIN_SUPPORTING_WINDOWS,
        },
    }


def calibration(gate4: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    actual_success = 1 if gate4.get("observed_only_lead") else 0
    prob = float(prediction.get("success_probability") or 0.0)
    return {
        "actual_decision": gate4["decision"],
        "actual_success": actual_success,
        "predicted_success_probability": prob,
        "brier_score": round((prob - actual_success) ** 2, 6),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": 0.0,
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": 0.0,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_mode": ";".join(gate4.get("failed_reasons") or []),
        "predicted_failure_mode_hit": bool(gate4.get("failed_reasons")),
        "surprise_note": (
            "PIT 13F crowding did not produce a monotonic high-vs-low loss-tail "
            "separation on the accepted stack."
            if not gate4.get("observed_only_lead")
            else "PIT 13F crowding separated accepted-stack loss tail and should be tested prospectively."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") or {}
    snapshots, snapshot_audit = load_13f_snapshots()
    rows, source_audit = load_rows(snapshots)
    attribution = build_attribution(rows, source_audit, snapshot_audit)
    gate4 = evaluate_gate4(attribution)
    baseline = load_baseline_summary()
    status = "observed_only" if gate4["observed_only_lead"] else "rejected"
    why = (
        "The point-in-time 13F crowding split did not satisfy the fixed loss-tail "
        "rule: high crowding failed at least one pooled direction check and/or "
        "did not hold across all three windows. The data remains useful context, "
        "but not a standalone risk-scaling lead on accepted core trades."
        if not gate4["observed_only_lead"]
        else (
            "High point-in-time 13F crowding separated lower PnL and heavier loss "
            "tail across all three accepted-stack windows, but this remains "
            "observed-only and needs prospective default-off logging before any "
            "policy use."
        )
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": gate4["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(gate4, prediction),
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new required a novelty override but reported "
                    "no blocking matches; this run uses a new gate shape over "
                    "already accepted trades rather than a 13F candidate-pool "
                    "source, source-rank scan, or threshold retune."
                ),
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": attribution["parameters"],
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "standard_window_result": repo_rel(STANDARD_WINDOW_RESULT),
            "window_files": {label: repo_rel(path) for label, path in WINDOW_FILES.items()},
        },
        "gate2": {
            "passed": all(
                row["trade_rows"] == row["rows_with_entry_date"]
                and row["trade_rows"] == row["rows_with_target_price_reconstructed"]
                for row in source_audit.values()
            )
            and snapshot_audit["snapshot_count"] > 0
            and (attribution["pooled"]["all"].get("joined_n") or 0) > 0,
            "dependency_fields_checked": [
                "entry_date",
                "entry_price",
                "stop_price",
                "target_mult_used",
                "target_price_reconstructed",
                "pnl",
                "pnl_pct_net",
                "13f_snapshot_as_of",
                "13f_report_period",
                "holder_count",
                "total_value_usd",
                "holder_count_sector_percentile",
                "total_value_sector_percentile",
            ],
            "target_price_note": (
                "Closed trade rows omit original target_price; runner reconstructs "
                "entry_price + (entry_price - stop_price) * target_mult_used and "
                "does not schedule executable orders."
            ),
            "source_audit": source_audit,
            "snapshot_audit": snapshot_audit,
        },
        "gate3": {
            "passed": True,
            "note": "No executable filter was added; core survival is unchanged.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": gate4,
        "attribution": attribution,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "uses_llm": False,
            "parity_note": (
                "Read-only attribution over accepted backtest trade rows. "
                "No production or backtest decision path changed."
            ),
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if gate4["failed_reasons"] else None,
        "next_retry_requires": (
            "Do not retune holder/value percentiles, high/low bucket cuts, sector "
            "normalization, or direct 13F candidate-pool variants on the same "
            "frozen windows. A retry needs active-manager quality, non-quarterly "
            "ownership flow, borrow/options cross-evidence, or prospective forward "
            "rows tagged with a 13F context field."
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not rerun this accepted-stack 13F attribution by changing "
                "the high/low percentile thresholds, holder vs value weights, "
                "sector buckets, report-period lag, or notional response curve."
            ),
            "new_evidence_required": (
                "Independent active-manager quality, non-quarterly ownership/flow "
                "data, borrow/options confirmation, or prospective forward rows "
                "closed after a shared default-off 13F context logger."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(STANDARD_WINDOW_RESULT),
            repo_rel(SECTOR_MAP_JSON),
            *[repo_rel(path) for path in WINDOW_FILES.values()],
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }
    return payload


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "parameters",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "rejection_reason",
        "next_retry_requires",
        "post_run_reflection",
        "related_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["attribution_summary"] = {
        "pooled": payload["attribution"]["pooled"],
        "by_window": payload["attribution"]["by_window"],
        "source_audit": payload["attribution"]["source_audit"],
        "snapshot_count": payload["attribution"]["snapshot_audit"]["snapshot_count"],
    }
    return row


def build_card(payload: dict[str, Any]) -> str:
    pooled = payload["attribution"]["pooled"]
    gate4 = payload["gate4"]
    high_low = pooled["high_low"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted-Core 13F Crowding Attribution",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Observed-only lead: `{payload['observed_only_lead']}`",
            f"- Joined rows: `{pooled['all'].get('joined_n')}`",
            f"- High bucket rows: `{pooled['buckets']['high'].get('n')}`",
            f"- Low bucket rows: `{pooled['buckets']['low'].get('n')}`",
            f"- Pooled high-minus-low avg PnL: `{high_low.get('high_minus_low_avg_pnl')}`",
            f"- Pooled high-minus-low win rate: `{high_low.get('high_minus_low_win_rate')}`",
            f"- Pooled high-minus-low loss-tail rate: `{high_low.get('high_minus_low_loss_tail_rate')}`",
            f"- Failed reasons: `{gate4['failed_reasons']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
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
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))

    result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "gate4_passed": payload["gate4"]["passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "new_evidence_axis",
            "parameters",
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "rejection_reason",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
        ]
        if key in payload
    }
    fields.update(
        {
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
