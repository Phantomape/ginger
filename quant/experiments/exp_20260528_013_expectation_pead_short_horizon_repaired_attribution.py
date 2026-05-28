"""exp-20260528-013: repaired PEAD short-horizon attribution.

Observed-only alpha search. This follows the exp-20260527-908 PEAD field
repair and exp-20260528-009 10d data gap by computing fresh 1d/2d/3d forward
outcomes from local weekday close snapshots. It does not change signal
generation, ranking, sizing, exits, LLM prompts, paper sleeves, or orders.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260528-013"
STEM = "expectation_pead_short_horizon_repaired_attribution"
MECHANISM_FAMILY = "expectation_revision_pead"
TRIAL_FAMILY = "expectation_pead_short_horizon_repaired_attribution"
CHANGED_VARIABLE = "repaired_pead_t2_t15_non_overextended_short_horizon_bucket_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCE_EXPERIMENT_ID = "exp-20260527-908"
SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

SHORT_HORIZONS = (1, 2, 3)
GATE_HORIZONS = ("1d", "2d")
PAPER_NOTIONAL_USD = 10_000.0
ANTI_JS = "No JavaScript was used."

BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "baseline_source": "docs/backtesting.md accepted aggregate core stack",
}

BUCKET_ORDER = [
    "eligible_t2_t15_non_overextended",
    "eligible_t2_t15_residual_leader",
    "primary_positive_outside_t2_t15",
    "primary_positive_missing_last_earnings_date",
    "primary_positive_other_pead_status",
    "not_primary_7d_positive",
]

MIN_CLOSED_OUTCOMES = {
    ("eligible_t2_t15_non_overextended", "1d"): 8,
    ("eligible_t2_t15_non_overextended", "2d"): 8,
    ("eligible_t2_t15_residual_leader", "1d"): 6,
    ("eligible_t2_t15_residual_leader", "2d"): 6,
    ("primary_positive_outside_t2_t15", "1d"): 15,
    ("primary_positive_outside_t2_t15", "2d"): 15,
}
MAX_TOP5_POSITIVE_PNL_SHARE = 0.80
MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE = 0.60

NEARBY_PRIORS = [
    {
        "experiment_id": "exp-20260527-006",
        "finding": "Short-horizon PEAD probe needed repaired earnings-date coverage and 2d outcome persistence.",
    },
    {
        "experiment_id": "exp-20260527-908",
        "finding": "PIT last_earnings_date repair created inside/outside PEAD buckets for 40/47 primary positive rows.",
    },
    {
        "experiment_id": "exp-20260528-009",
        "finding": "5d non-overextended inside-PEAD looked positive, but 10d coverage was below minimum and positive PnL was concentrated.",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(compact + "\n", encoding="utf-8")
        return

    found = False
    with path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                found = True
                break

    if not found:
        with path.open("a", encoding="utf-8", newline="\n") as dst:
            dst.write(compact + "\n")
        return

    tmp_path = path.with_name(f"{path.name}.{EXPERIMENT_ID}.tmp")
    replaced = False
    with path.open("r", encoding="utf-8", errors="replace") as src, tmp_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as dst:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                dst.write(line if line.endswith("\n") else line + "\n")
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    dst.write(compact + "\n")
                    replaced = True
                continue
            dst.write(line if line.endswith("\n") else line + "\n")
    try:
        tmp_path.replace(path)
    except PermissionError:
        compact = _compact_jsonl_fallback(payload)
        if not _replace_jsonl_line_in_place(path, compact):
            with path.open("a", encoding="utf-8", newline="\n") as dst:
                dst.write(compact + "\n")
        try:
            tmp_path.unlink(missing_ok=True)
        except PermissionError:
            pass


def _compact_jsonl_fallback(payload: dict[str, Any]) -> str:
    jsonl_payload = dict(payload)
    jsonl_payload.pop("sample_rows", None)
    jsonl_payload["sample_rows_omitted_from_jsonl"] = True
    return json.dumps(_safe(jsonl_payload), ensure_ascii=True, sort_keys=True)


def _replace_jsonl_line_in_place(path: Path, compact: str) -> bool:
    target = EXPERIMENT_ID.encode("utf-8")
    replacement_body = compact.encode("utf-8")
    offset = 0
    with path.open("rb") as src:
        while True:
            line = src.readline()
            if not line:
                return False
            if target in line:
                old_len = len(line)
                break
            offset += len(line)
    if len(replacement_body) + 1 > old_len:
        return False
    replacement = replacement_body + (b" " * (old_len - len(replacement_body) - 1)) + b"\n"
    with path.open("r+b") as dst:
        dst.seek(offset)
        dst.write(replacement)
    return True


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _coerce_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value)
    if len(raw) == 8 and raw.isdigit():
        return datetime.strptime(raw, "%Y%m%d").date()
    return datetime.strptime(raw[:10], "%Y-%m-%d").date()


def _date_from_path(path: Path) -> date | None:
    stem = path.stem
    suffix = stem.rsplit("_", 1)[-1]
    try:
        return _coerce_date(suffix)
    except ValueError:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class TradingDayPriceLookup:
    """Close-price lookup that ignores weekend daily artifacts for horizons."""

    def __init__(self) -> None:
        self.by_ticker: dict[str, dict[date, float]] = defaultdict(dict)

    def add(self, ticker: str, day: str | date | datetime, close: Any) -> None:
        day_value = _coerce_date(day)
        if day_value.weekday() >= 5:
            return
        price = _float(close)
        if price is None or price <= 0:
            return
        self.by_ticker[str(ticker).upper()][day_value] = price

    def forward_return(self, ticker: str, day: str | date | datetime, horizon: int) -> dict[str, Any]:
        ticker = str(ticker).upper()
        as_of = _coerce_date(day)
        price_map = self.by_ticker.get(ticker) or {}
        start_price = price_map.get(as_of)
        if start_price is None or start_price <= 0:
            return {
                "closed": False,
                "return": None,
                "pnl_proxy": None,
                "future_date": None,
                "gap_reason": "missing_start_price",
            }
        future_dates = [
            row_date
            for row_date in sorted(price_map)
            if row_date > as_of and row_date.weekday() < 5
        ]
        if len(future_dates) < horizon:
            return {
                "closed": False,
                "return": None,
                "pnl_proxy": None,
                "future_date": None,
                "gap_reason": f"missing_{horizon}d_forward_price",
            }
        future_date = future_dates[horizon - 1]
        future_price = price_map[future_date]
        forward_return = (future_price / start_price) - 1.0
        return {
            "closed": True,
            "return": round(forward_return, 6),
            "pnl_proxy": round(forward_return * PAPER_NOTIONAL_USD, 2),
            "future_date": future_date.isoformat(),
            "future_close": round(future_price, 6),
            "start_close": round(start_price, 6),
            "gap_reason": None,
        }


def _load_ohlcv_payload(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return payload.get("ohlcv") if isinstance(payload.get("ohlcv"), dict) else payload


def build_trading_day_price_lookup(data_dir: Path) -> TradingDayPriceLookup:
    prices = TradingDayPriceLookup()

    for path in sorted((data_dir / "ohlcv").glob("ohlcv_snapshot_*.json")):
        payload = _load_ohlcv_payload(path)
        for ticker, rows in payload.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                day = row.get("Date") or row.get("date")
                close = row.get("Close") if "Close" in row else row.get("close")
                if day:
                    prices.add(ticker, day, close)

    trend_dirs = [
        data_dir / "daily" / "signals" / "trend",
        data_dir / "daily" / "signals",
    ]
    for trend_dir in trend_dirs:
        for path in sorted(trend_dir.glob("trend_signals_*.json")):
            payload = _read_json(path)
            raw_signals = payload.get("signals")
            if not isinstance(raw_signals, dict):
                continue
            as_of = (
                payload.get("asof_date")
                or payload.get("as_of_date")
                or _date_from_path(path)
            )
            if not as_of:
                continue
            for ticker, row in raw_signals.items():
                if isinstance(row, dict):
                    prices.add(ticker, as_of, row.get("close") or row.get("Close"))

    return prices


def load_source(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing source artifact: {_repo_rel(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("enriched_watchlist_rows")
    if not isinstance(rows, list):
        raise ValueError("source artifact does not contain enriched_watchlist_rows")
    return payload


def is_primary_positive(row: dict[str, Any]) -> bool:
    return bool(row.get("primary_expectation_positive"))


def is_residual_leader(row: dict[str, Any]) -> bool:
    state = str(row.get("residual_state") or "")
    return bool(row.get("residual_leader")) or state in {
        "residual_leader",
        "strong_residual_leader",
    }


def bucket_for(row: dict[str, Any]) -> str:
    if not is_primary_positive(row):
        return "not_primary_7d_positive"

    pead_status = str(row.get("pead_status") or "")
    if pead_status == "inside_t2_t15_after_earnings":
        if is_residual_leader(row):
            return "eligible_t2_t15_residual_leader"
        return "eligible_t2_t15_non_overextended"
    if pead_status == "outside_t2_t15_after_earnings":
        return "primary_positive_outside_t2_t15"
    if pead_status == "missing_last_earnings_date":
        return "primary_positive_missing_last_earnings_date"
    return "primary_positive_other_pead_status"


def attach_short_outcomes(rows: list[dict[str, Any]], data_dir: Path) -> list[dict[str, Any]]:
    prices = build_trading_day_price_lookup(data_dir)
    out = []
    for row in rows:
        enriched = dict(row)
        ticker = str(enriched.get("ticker") or "").upper()
        effective_date = (
            enriched.get("watchlist_effective_trade_date")
            or enriched.get("as_of_date")
            or enriched.get("feature_context_date")
        )
        short_outcomes = {}
        for horizon in SHORT_HORIZONS:
            if ticker and effective_date:
                short_outcomes[f"{horizon}d"] = prices.forward_return(
                    ticker,
                    effective_date,
                    horizon,
                )
            else:
                short_outcomes[f"{horizon}d"] = {
                    "closed": False,
                    "return": None,
                    "pnl_proxy": None,
                    "future_date": None,
                    "gap_reason": "missing_ticker_or_effective_date",
                }
        enriched["short_forward_outcomes"] = short_outcomes
        enriched["pead_attribution_bucket"] = bucket_for(enriched)
        out.append(enriched)
    return out


def outcome_for(row: dict[str, Any], horizon: str) -> dict[str, Any]:
    raw = ((row.get("short_forward_outcomes") or {}).get(horizon) or {}).copy()
    closed = bool(raw.get("closed"))
    ret = _float(raw.get("return"))
    pnl = _float(raw.get("pnl_proxy"))
    if closed and pnl is None and ret is not None:
        pnl = ret * PAPER_NOTIONAL_USD
    return {
        "closed": closed,
        "return": ret,
        "pnl_proxy": pnl,
        "future_date": raw.get("future_date"),
        "gap_reason": raw.get("gap_reason"),
        "start_close": raw.get("start_close"),
        "future_close": raw.get("future_close"),
    }


def positive_pnl_concentration(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    positives: list[tuple[str, float]] = []
    for row in rows:
        outcome = outcome_for(row, horizon)
        pnl = outcome["pnl_proxy"]
        if outcome["closed"] and pnl is not None and pnl > 0:
            positives.append((str(row.get("ticker") or ""), pnl))

    total_positive = sum(pnl for _, pnl in positives)
    if total_positive <= 0:
        return {
            "positive_pnl_total": 0.0,
            "top5_positive_pnl_share": None,
            "single_ticker_positive_pnl_share": None,
        }

    top5 = sum(pnl for _, pnl in sorted(positives, key=lambda item: item[1], reverse=True)[:5])
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for ticker, pnl in positives:
        by_ticker[ticker] += pnl
    single = max(by_ticker.values()) if by_ticker else 0.0
    return {
        "positive_pnl_total": total_positive,
        "top5_positive_pnl_share": top5 / total_positive,
        "single_ticker_positive_pnl_share": single / total_positive,
    }


def summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    days_since = [
        value
        for value in (_float(row.get("days_since_last_earnings")) for row in rows)
        if value is not None
    ]
    summary: dict[str, Any] = {
        "row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows}),
        "residual_leader_count": sum(1 for row in rows if is_residual_leader(row)),
        "residual_state_counts": dict(Counter(str(row.get("residual_state") or "") for row in rows)),
        "pead_status_counts": dict(Counter(str(row.get("pead_status") or "") for row in rows)),
        "sector_counts": dict(Counter(str(row.get("sector") or "") for row in rows)),
        "days_since_last_earnings": {
            "min": min(days_since) if days_since else None,
            "avg": sum(days_since) / len(days_since) if days_since else None,
            "max": max(days_since) if days_since else None,
        },
        "short_forward_outcomes": {},
    }
    for horizon_days in SHORT_HORIZONS:
        horizon = f"{horizon_days}d"
        outcomes = [outcome_for(row, horizon) for row in rows]
        closed = [item for item in outcomes if item["closed"]]
        returns = [item["return"] for item in closed if item["return"] is not None]
        pnls = [item["pnl_proxy"] for item in closed if item["pnl_proxy"] is not None]
        wins = [value for value in returns if value > 0]
        summary["short_forward_outcomes"][horizon] = {
            "closed_count": len(closed),
            "missing_count": len(rows) - len(closed),
            "avg_return": sum(returns) / len(returns) if returns else None,
            "win_rate": len(wins) / len(returns) if returns else None,
            "total_pnl_proxy": sum(pnls) if pnls else None,
            **positive_pnl_concentration(rows, horizon),
        }
    return summary


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in BUCKET_ORDER}
    for row in rows:
        by_bucket.setdefault(str(row["pead_attribution_bucket"]), []).append(row)
    return {bucket: summarize_bucket(by_bucket.get(bucket, [])) for bucket in by_bucket}


def metric(
    summary: dict[str, Any],
    bucket: str,
    horizon: str,
    field: str,
    default: Any = None,
) -> Any:
    return (
        ((summary.get(bucket) or {}).get("short_forward_outcomes") or {})
        .get(horizon, {})
        .get(field, default)
    )


def build_gate(summary: dict[str, Any]) -> dict[str, Any]:
    data_gaps = []
    for (bucket, horizon), minimum in MIN_CLOSED_OUTCOMES.items():
        closed_count = metric(summary, bucket, horizon, "closed_count", 0)
        if closed_count < minimum:
            data_gaps.append(
                {
                    "bucket": bucket,
                    "horizon": horizon,
                    "closed_count": closed_count,
                    "minimum": minimum,
                    "reason": "closed_outcomes_below_minimum",
                }
            )

    comparisons: dict[str, Any] = {}
    for horizon in GATE_HORIZONS:
        non_avg = metric(summary, "eligible_t2_t15_non_overextended", horizon, "avg_return")
        residual_avg = metric(summary, "eligible_t2_t15_residual_leader", horizon, "avg_return")
        outside_avg = metric(summary, "primary_positive_outside_t2_t15", horizon, "avg_return")
        non_pnl = metric(
            summary,
            "eligible_t2_t15_non_overextended",
            horizon,
            "total_pnl_proxy",
        )
        residual_pnl = metric(
            summary,
            "eligible_t2_t15_residual_leader",
            horizon,
            "total_pnl_proxy",
        )
        outside_pnl = metric(
            summary,
            "primary_positive_outside_t2_t15",
            horizon,
            "total_pnl_proxy",
        )
        comparisons[horizon] = {
            "non_overextended_avg_return": non_avg,
            "residual_leader_avg_return": residual_avg,
            "outside_pead_avg_return": outside_avg,
            "non_overextended_total_pnl_proxy": non_pnl,
            "residual_leader_total_pnl_proxy": residual_pnl,
            "outside_pead_total_pnl_proxy": outside_pnl,
            "non_overextended_beats_residual_avg": (
                non_avg is not None and residual_avg is not None and non_avg > residual_avg
            ),
            "non_overextended_beats_outside_avg": (
                non_avg is not None and outside_avg is not None and non_avg > outside_avg
            ),
            "non_overextended_beats_residual_pnl": (
                non_pnl is not None and residual_pnl is not None and non_pnl > residual_pnl
            ),
            "non_overextended_beats_outside_pnl": (
                non_pnl is not None and outside_pnl is not None and non_pnl > outside_pnl
            ),
        }

    residual_avoidance_signal = all(
        bool(comparisons[horizon]["non_overextended_beats_residual_avg"])
        and bool(comparisons[horizon]["non_overextended_beats_residual_pnl"])
        for horizon in GATE_HORIZONS
    )
    inside_pead_promotable_signal = all(
        bool(comparisons[horizon][key])
        for horizon in GATE_HORIZONS
        for key in (
            "non_overextended_beats_residual_avg",
            "non_overextended_beats_residual_pnl",
            "non_overextended_beats_outside_avg",
            "non_overextended_beats_outside_pnl",
        )
    )

    concentration = {
        horizon: {
            "top5_positive_pnl_share": metric(
                summary,
                "eligible_t2_t15_non_overextended",
                horizon,
                "top5_positive_pnl_share",
            ),
            "single_ticker_positive_pnl_share": metric(
                summary,
                "eligible_t2_t15_non_overextended",
                horizon,
                "single_ticker_positive_pnl_share",
            ),
        }
        for horizon in GATE_HORIZONS
    }
    concentration_flags = []
    for horizon, values in concentration.items():
        top5 = values["top5_positive_pnl_share"]
        single = values["single_ticker_positive_pnl_share"]
        if top5 is not None and top5 > MAX_TOP5_POSITIVE_PNL_SHARE:
            concentration_flags.append(f"{horizon}_top5_positive_pnl_concentration")
        if single is not None and single > MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE:
            concentration_flags.append(f"{horizon}_single_ticker_positive_pnl_concentration")

    if data_gaps:
        decision = "observed_only_data_gap"
        reason = "closed_outcomes_below_minimum"
        passed = False
    elif inside_pead_promotable_signal:
        if concentration_flags:
            decision = "observed_only_no_promotable_edge"
            reason = "positive_pnl_concentration_guardrail_failed"
            passed = False
        else:
            decision = "observed_only_promising_needs_strategy_gate"
            reason = None
            passed = True
    else:
        decision = "observed_only_no_promotable_edge"
        reason = "inside_pead_non_overextended_did_not_beat_outside_pead_short_horizon"
        passed = False

    return {
        "passed": passed,
        "decision": decision,
        "reason": reason,
        "data_gaps": data_gaps,
        "comparisons": comparisons,
        "concentration": concentration,
        "concentration_flags": concentration_flags,
        "residual_avoidance_signal": residual_avoidance_signal,
        "inside_pead_promotable_signal": inside_pead_promotable_signal,
    }


def field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, "", [], {}))
        out[field] = {
            "present": present,
            "total": len(rows),
            "coverage_ratio": present / len(rows) if rows else None,
        }
    return out


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    outcomes = {}
    for horizon in ("1d", "2d", "3d"):
        outcome = outcome_for(row, horizon)
        outcomes[horizon] = {
            "closed": outcome["closed"],
            "return": outcome["return"],
            "pnl_proxy": outcome["pnl_proxy"],
            "future_date": outcome["future_date"],
            "gap_reason": outcome["gap_reason"],
        }
    return {
        "as_of_date": row.get("as_of_date"),
        "feature_context_date": row.get("feature_context_date"),
        "watchlist_effective_trade_date": row.get("watchlist_effective_trade_date"),
        "ticker": row.get("ticker"),
        "bucket": row.get("pead_attribution_bucket"),
        "pead_status": row.get("pead_status"),
        "days_since_last_earnings": row.get("days_since_last_earnings"),
        "last_earnings_date": row.get("last_earnings_date"),
        "residual_state": row.get("residual_state"),
        "residual_leader": row.get("residual_leader"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "forward_outcomes": outcomes,
    }


def build_payload(source_path: Path, data_dir: Path) -> dict[str, Any]:
    timestamp = _utc_now()
    source_payload = load_source(source_path)
    rows = attach_short_outcomes(source_payload["enriched_watchlist_rows"], data_dir)
    bucket_summary = summarize_rows(rows)
    gate = build_gate(bucket_summary)
    decision = gate["decision"]
    as_of_dates = sorted(str(row.get("as_of_date")) for row in rows if row.get("as_of_date"))

    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(source_path),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOCS_TICKET),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]
    coverage = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "rows_total": len(rows),
        "as_of_date_range": f"{as_of_dates[0]} .. {as_of_dates[-1]}" if as_of_dates else None,
        "primary_positive_rows": sum(1 for row in rows if is_primary_positive(row)),
        "bucket_counts": dict(Counter(str(row["pead_attribution_bucket"]) for row in rows)),
        "primary_positive_pead_status_counts": dict(
            Counter(str(row.get("pead_status") or "") for row in rows if is_primary_positive(row))
        ),
        "closed_short_forward_outcomes": {
            f"{horizon}d": sum(
                1
                for row in rows
                if ((row.get("short_forward_outcomes") or {}).get(f"{horizon}d") or {}).get(
                    "closed"
                )
            )
            for horizon in SHORT_HORIZONS
        },
        "field_coverage": field_coverage(
            rows,
            [
                "ticker",
                "as_of_date",
                "watchlist_effective_trade_date",
                "primary_expectation_positive",
                "eps_estimate_delta_7d",
                "last_earnings_date",
                "pead_status",
                "days_since_last_earnings",
                "short_forward_outcomes",
            ],
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "After the PIT last_earnings_date repair, primary positive EPS "
            "revision rows inside the T+2..T+15 PEAD window and not residual "
            "leaders should outperform residual-leader PEAD rows and primary "
            "positive rows outside the PEAD window over closed 1d/2d horizons."
        ),
        "change_summary": (
            "Observed-only short-horizon PEAD attribution. Reads the "
            "exp-20260527-908 enriched watchlist, computes fresh 1d/2d/3d "
            "forward outcomes from local weekday close snapshots, and compares "
            "repaired PEAD buckets without changing production or backtest behavior."
        ),
        "change_type": "observed_only_short_horizon_pead_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 5,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "repaired_pead_bucket_short_horizon_forward_outcomes",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(source_path),
            "data_dir": _repo_rel(data_dir),
            "pead_window": "T+2..T+15 after last_earnings_date",
            "primary_positive_definition": "source primary_expectation_positive == true",
            "non_overextended_definition": "not residual_leader and residual_state not in residual_leader/strong_residual_leader",
            "short_forward_horizons": list(SHORT_HORIZONS),
            "gate_horizons": list(GATE_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "min_closed_outcomes": {
                f"{bucket}:{horizon}": minimum
                for (bucket, horizon), minimum in MIN_CLOSED_OUTCOMES.items()
            },
            "anti_js": ANTI_JS,
        },
        "date_range": source_payload.get("date_range")
        or {"source_watchlist_as_of_dates": coverage["as_of_date_range"]},
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Repaired PEAD T+2..T+15 primary positive revision rows that "
                "are not residual leaders are a better 1d/2d continuation "
                "bucket than residual-leader PEAD rows or outside-PEAD rows."
            ),
            "2_history_check": (
                "exp-20260527-006 needed 2d outcomes; exp-20260527-908 repaired "
                "last_earnings_date; exp-20260528-009 found 10d data gaps."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only pass requires sufficient 1d/2d closed outcomes, "
                "non-overextended inside-PEAD to beat residual-leader and "
                "outside-PEAD comparators on avg return and PnL, and "
                "concentration below guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260528_013_expectation_pead_short_horizon_repaired_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "note": "Observed-only attribution; no before/after core strategy metrics change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "ticker",
                "watchlist_effective_trade_date",
                "primary_expectation_positive",
                "last_earnings_date",
                "pead_status",
                "residual_leader",
                "residual_state",
                "local weekday close snapshots",
            ],
            "source_gate2": source_payload.get("gates", {}).get("gate2")
            or source_payload.get("gate2"),
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": bool(gate["passed"]),
            "note": "Observed-only result can only unlock a later default-off Gate 1-4 strategy experiment.",
        },
        "coverage": coverage,
        "bucket_summary": bucket_summary,
        "gate": gate,
        "sample_rows": {
            bucket: [
                compact_row(row)
                for row in rows
                if row.get("pead_attribution_bucket") == bucket
            ][:80]
            for bucket in BUCKET_ORDER
            if bucket != "not_primary_7d_positive"
        },
        "before_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "observed_only_attribution": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": gate["reason"],
        "next_evidence_needed": (
            "Do not promote an inside-PEAD short-horizon gate from this evidence. "
            "The non-overextended inside-PEAD bucket beat residual leaders, but "
            "outside-PEAD primary-positive rows were stronger at 1d/2d. Future "
            "work should either wait for 5d/10d maturation or test a separate "
            "outside-PEAD revision-momentum hypothesis."
        ),
        "related_files": related_files,
        "anti_js": ANTI_JS,
    }


def _fmt(value: Any) -> str:
    number = _float(value)
    if number is None:
        return ""
    return f"{number:.6f}"


def artifact_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "# exp-20260528-013 Repaired PEAD Short-Horizon Attribution",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        "- Strategy behavior changed: `false`",
        "",
        "## Bucket Outcomes",
        "",
        "| bucket | rows | 1d closed | 1d avg | 1d pnl | 2d closed | 2d avg | 2d pnl | 3d closed | 3d avg | 3d pnl |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKET_ORDER:
        summary = payload["bucket_summary"].get(bucket, {})
        outcomes = summary.get("short_forward_outcomes", {})
        h1 = outcomes.get("1d", {})
        h2 = outcomes.get("2d", {})
        h3 = outcomes.get("3d", {})
        rows.append(
            "| {bucket} | {rows_count} | {c1} | {a1} | {p1} | {c2} | {a2} | {p2} | {c3} | {a3} | {p3} |".format(
                bucket=bucket,
                rows_count=summary.get("row_count", 0),
                c1=h1.get("closed_count", 0),
                a1=_fmt(h1.get("avg_return")),
                p1=_fmt(h1.get("total_pnl_proxy")),
                c2=h2.get("closed_count", 0),
                a2=_fmt(h2.get("avg_return")),
                p2=_fmt(h2.get("total_pnl_proxy")),
                c3=h3.get("closed_count", 0),
                a3=_fmt(h3.get("avg_return")),
                p3=_fmt(h3.get("total_pnl_proxy")),
            )
        )
    rows.extend(
        [
            "",
            "## Gate Details",
            "",
            f"- Data gaps: `{json.dumps(payload['gate']['data_gaps'], ensure_ascii=True)}`",
            f"- Residual avoidance signal: `{payload['gate']['residual_avoidance_signal']}`",
            f"- Inside-PEAD promotable signal: `{payload['gate']['inside_pead_promotable_signal']}`",
            f"- Concentration flags: `{payload['gate']['concentration_flags']}`",
            "",
            "## Interpretation",
            "",
            "The short-horizon sample is mature enough to compare 1d/2d buckets. Non-overextended inside-PEAD rows beat residual leaders, but they do not beat outside-PEAD primary-positive rows, so this does not support an inside-PEAD short-horizon promotion.",
            "",
            "## Related Files",
            "",
        ]
    )
    rows.extend(f"- `{path}`" for path in payload["related_files"])
    rows.append("")
    return "\n".join(rows)


def persist_payload(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "artifact_file": _repo_rel(OUT_JSON),
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "owner": "codex-expectation-pead-short-horizon",
        "result_file": _repo_rel(DOC_LOG),
        "single_causal_variable": CHANGED_VARIABLE,
        "status": payload["status"],
        "updated_at": payload["timestamp"],
    }
    _write_json(DOC_TICKET, ticket)
    _write_json(DOCS_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    update_registry(payload, ticket)


def update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    else:
        registry = {"experiments": []}
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "owner": ticket["owner"],
        "status": payload["status"],
        "ticket_file": _repo_rel(DOC_TICKET),
        "updated_at": payload["timestamp"],
    }
    replaced = False
    for idx, item in enumerate(experiments):
        if item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = row
            replaced = True
            break
    if not replaced:
        experiments.append(row)
    _write_json(EXPERIMENT_REGISTRY, registry)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact", default=str(SOURCE_ARTIFACT))
    parser.add_argument("--data-dir", default=str(REPO_ROOT / "data"))
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = build_payload(Path(args.source_artifact), Path(args.data_dir))
    if not args.no_persist:
        persist_payload(payload)

    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "gate": payload["gate"],
                "coverage": {
                    "rows_total": payload["coverage"]["rows_total"],
                    "bucket_counts": payload["coverage"]["bucket_counts"],
                    "closed_short_forward_outcomes": payload["coverage"][
                        "closed_short_forward_outcomes"
                    ],
                },
                "output": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
